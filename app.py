from flask import Flask, request, jsonify
import requests
import os
import hmac
import hashlib
import logging
import json
from datetime import datetime, timedelta
import threading
import time
from dotenv import load_dotenv
from db_handler import DatabaseHandler

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
GITHUB_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET')
STALE_PR_DAYS = int(os.getenv('STALE_PR_DAYS', '7'))  # Default to 7 days

def verify_github_webhook(request):
    """
    Verify that the webhook request came from GitHub
    """
    logger.debug("Starting webhook verification")
    
    # Get headers
    received_signature = request.headers.get('X-Hub-Signature-256')
    logger.debug(f"Received X-Hub-Signature-256: {received_signature}")
    
    if not received_signature:
        logger.error("No X-Hub-Signature-256 found in headers")
        return False

    # Get payload
    payload_body = request.get_data()
    logger.debug(f"Payload length: {len(payload_body)} bytes")
    
    if not GITHUB_SECRET:
        logger.error("GITHUB_SECRET not configured")
        return False
        
    try:
        # Calculate signature
        secret_bytes = GITHUB_SECRET.encode('utf-8')
        hmac_gen = hmac.new(secret_bytes, payload_body, hashlib.sha256)
        expected_signature = f"sha256={hmac_gen.hexdigest()}"
        logger.debug(f"Expected signature: {expected_signature}")
        logger.debug(f"Received signature: {received_signature}")
        
        return hmac.compare_digest(received_signature, expected_signature)
    except Exception as e:
        logger.error(f"Error during signature verification: {str(e)}")
        return False

def send_slack_notification(title, text, fields=None, actions=None):
    """
    Send a notification to the Slack webhook
    """
    try:
        if not SLACK_WEBHOOK_URL:
            logger.error("SLACK_WEBHOOK_URL not configured")
            return False
            
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": title
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            }
        ]
        
        # Add fields if provided
        if fields:
            field_block = {
                "type": "section",
                "fields": []
            }
            for field in fields:
                field_block["fields"].append({
                    "type": "mrkdwn",
                    "text": field
                })
            blocks.append(field_block)
        
        # Add actions if provided
        if actions:
            action_block = {
                "type": "actions",
                "elements": []
            }
            for action in actions:
                action_block["elements"].append({
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": action["text"]
                    },
                    "url": action["url"]
                })
            blocks.append(action_block)
        
        message = {
            "blocks": blocks
        }
        
        logger.debug("Sending notification to Slack")
        response = requests.post(SLACK_WEBHOOK_URL, json=message)
        logger.debug(f"Slack API Response: {response.status_code} - {response.text}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error sending Slack notification: {str(e)}")
        return False

def process_pull_request(data):
    """
    Process pull request event data and store in database
    """
    try:
        db = DatabaseHandler()
        
        # Check if database connection was successful
        if hasattr(db, 'connection_failed') and db.connection_failed:
            logger.error("Database connection failed, skipping PR processing")
            return None
            
        # Extract repository and user info
        repo_data = data.get('repository')
        pr_data = data.get('pull_request')
        
        if not repo_data or not pr_data:
            logger.error("Missing repository or PR data")
            return None
            
        user_data = pr_data.get('user')
        
        if not user_data:
            logger.error("Missing user data in PR")
            return None
        
        # Store in database
        repo_id = db.get_or_create_repository(repo_data)
        user_id = db.get_or_create_user(user_data)
        
        if repo_id is None or user_id is None:
            logger.error(f"Failed to get or create repository or user: repo_id={repo_id}, user_id={user_id}")
            db.close()
            return None
            
        pr_id = db.get_or_create_pull_request(pr_data, repo_id, user_id)
        
        db.close()
        return pr_id
    except Exception as e:
        logger.error(f"Error processing pull request: {str(e)}")
        return None

def process_review(data):
    """
    Process pull request review event data and store in database
    """
    try:
        db = DatabaseHandler()
        
        # Check if database connection was successful
        if hasattr(db, 'connection_failed') and db.connection_failed:
            logger.error("Database connection failed, skipping review processing")
            return None
            
        # Extract repository, user, PR, and review info
        repo_data = data.get('repository')
        review_data = data.get('review')
        pr_data = data.get('pull_request')
        
        if not repo_data or not review_data or not pr_data:
            logger.error("Missing repository, review, or PR data")
            return None
            
        reviewer_data = review_data.get('user')
        pr_author_data = pr_data.get('user')
        
        if not reviewer_data or not pr_author_data:
            logger.error("Missing reviewer or PR author data")
            return None
        
        # Store in database
        repo_id = db.get_or_create_repository(repo_data)
        reviewer_id = db.get_or_create_user(reviewer_data)
        pr_author_id = db.get_or_create_user(pr_author_data)
        
        if repo_id is None or reviewer_id is None or pr_author_id is None:
            logger.error("Failed to get or create repository, reviewer, or PR author")
            db.close()
            return None
            
        pr_id = db.get_or_create_pull_request(pr_data, repo_id, pr_author_id)
        
        if pr_id is None:
            logger.error("Failed to get or create pull request")
            db.close()
            return None
            
        review_id = db.add_pr_review(review_data, pr_id, reviewer_id)
        
        db.close()
        return review_id
    except Exception as e:
        logger.error(f"Error processing review: {str(e)}")
        return None

def check_stale_prs():
    """
    Check for stale PRs and send notifications
    """
    try:
        db = DatabaseHandler()
        
        # Check if database connection was successful
        if hasattr(db, 'connection_failed') and db.connection_failed:
            logger.error("Database connection failed, skipping stale PR check")
            return
            
        newly_stale_pr_ids = db.check_for_stale_prs(STALE_PR_DAYS)
        
        if newly_stale_pr_ids:
            stale_prs = db.get_stale_prs()
            
            if stale_prs:
                # Notify about stale PRs
                title = "🚨 Stale Pull Requests Detected"
                text = f"The following pull requests have been inactive for {STALE_PR_DAYS} days:"
                
                fields = []
                actions = []
                
                # Only include up to 10 PRs to avoid Slack message size limits
                for i, pr in enumerate(stale_prs[:10]):
                    pr_id, pr_title, pr_number, pr_url, repo_name, username, created_at, last_activity = pr
                    
                    days_inactive = (datetime.now() - last_activity).days if isinstance(last_activity, datetime) else '?'
                    fields.append(f"*{repo_name} #{pr_number}*: {pr_title}")
                    fields.append(f"Created by: {username} | Inactive for {days_inactive} days")
                    
                    actions.append({
                        "text": f"View #{pr_number}",
                        "url": pr_url
                    })
                
                # If there are more than 10 stale PRs, add a note
                if len(stale_prs) > 10:
                    text += f"\n\n*Note: Showing 10 of {len(stale_prs)} stale PRs*"
                
                send_slack_notification(title, text, fields, actions)
        
        db.close()
    except Exception as e:
        logger.error(f"Error checking for stale PRs: {str(e)}")

def process_review_comment(data):
    """
    Process pull request review comment and store in database
    """
    try:
        db = DatabaseHandler()
        
        # Check if database connection was successful
        if hasattr(db, 'connection_failed') and db.connection_failed:
            logger.error("Database connection failed, skipping comment processing")
            return None
            
        # Extract repository, user, PR, and comment info
        repo_data = data.get('repository')
        comment_data = data.get('comment')
        pr_data = data.get('pull_request')
        
        if not repo_data or not comment_data or not pr_data:
            logger.error("Missing repository, comment, or PR data")
            return None
            
        commenter_data = comment_data.get('user')
        pr_author_data = pr_data.get('user')
        
        if not commenter_data or not pr_author_data:
            logger.error("Missing commenter or PR author data")
            return None
        
        # Store in database
        repo_id = db.get_or_create_repository(repo_data)
        commenter_id = db.get_or_create_user(commenter_data)
        pr_author_id = db.get_or_create_user(pr_author_data)
        
        if repo_id is None or commenter_id is None or pr_author_id is None:
            logger.error("Failed to get or create repository, commenter, or PR author")
            db.close()
            return None
            
        pr_id = db.get_or_create_pull_request(pr_data, repo_id, pr_author_id)
        
        if pr_id is None:
            logger.error("Failed to get or create pull request")
            db.close()
            return None
        
        # Check if this comment is associated with a review
        review_id = None
        if comment_data.get('pull_request_review_id'):
            # In a real implementation, you might want to look up the review_id in your DB
            # For simplicity, we'll pass None for now
            pass
        
        comment_id = db.add_review_comment(comment_data, pr_id, commenter_id, review_id)
        
        db.close()
        return comment_id
    except Exception as e:
        logger.error(f"Error processing review comment: {str(e)}")
        return None

# Background task for checking stale PRs
def stale_pr_checker():
    """Background thread to check for stale PRs on a schedule"""
    while True:
        logger.info("Running scheduled stale PR check")
        check_stale_prs()
        # Sleep for 1 day (86400 seconds)
        time.sleep(86400)

# Route handlers
@app.route('/', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/', methods=['POST'])
def handle_webhook():
    """
    Handle GitHub webhook events
    """
    logger.info("Received webhook request")
    logger.debug(f"Request Headers: {dict(request.headers)}")
    
    # Verify webhook signature
    if not verify_github_webhook(request):
        logger.error("Webhook verification failed")
        return jsonify({"error": "Invalid signature"}), 400
    
    try:
        data = request.get_json()
        event_type = request.headers.get('X-GitHub-Event')
        logger.info(f"Event type: {event_type}")
        
        # Handle different event types
        if event_type == 'pull_request':
            action = data.get('action')
            logger.info(f"Pull request action: {action}")
            
            if action in ['opened', 'reopened', 'synchronize', 'edited']:
                pr_id = process_pull_request(data)
                
                # Send notification for new PRs
                if action == 'opened' and SLACK_WEBHOOK_URL:
                    pr = data['pull_request']
                    repo = data['repository']
                    
                    title = "🔔 New Pull Request Created"
                    text = f"*{pr['title']}*\n{pr.get('body', 'No description provided.')}"
                    
                    fields = [
                        f"*Repository:* {repo['full_name']}",
                        f"*Created by:* {pr['user']['login']}"
                    ]
                    
                    actions = [{
                        "text": "View Pull Request",
                        "url": pr['html_url']
                    }]
                    
                    send_slack_notification(title, text, fields, actions)
                
                return jsonify({"status": "success", "message": "PR processed"}), 200
                
        elif event_type == 'pull_request_review':
            review_id = process_review(data)
            
            # Send notification for requested changes
            if data['review']['state'] == 'changes_requested' and SLACK_WEBHOOK_URL:
                pr = data['pull_request']
                review = data['review']
                repo = data['repository']
                
                title = "⚠️ Changes Requested on Pull Request"
                text = f"*{pr['title']}*\n{review.get('body', 'No review comments provided.')}"
                
                fields = [
                    f"*Repository:* {repo['full_name']}",
                    f"*PR Author:* {pr['user']['login']}",
                    f"*Reviewer:* {review['user']['login']}"
                ]
                
                actions = [{
                    "text": "View Review",
                    "url": review['html_url']
                }]
                
                send_slack_notification(title, text, fields, actions)
            
            return jsonify({"status": "success", "message": "Review processed"}), 200
            
        elif event_type == 'pull_request_review_comment':
            comment_id = process_review_comment(data)
            return jsonify({"status": "success", "message": "Comment processed"}), 200
        
        # Handle ping event (GitHub sends this when webhook is first configured)
        elif event_type == 'ping':
            return jsonify({"status": "success", "message": "Pong!"}), 200
            
        return jsonify({"status": "success", "message": "Event received"}), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({"error": f"Error processing webhook: {str(e)}"}), 500

if __name__ == '__main__':
    # Verify environment variables
    missing_vars = []
    if not GITHUB_SECRET:
        missing_vars.append("GITHUB_WEBHOOK_SECRET")
    
    if not os.getenv('DATABASE_CONNECTION_STRING'):
        missing_vars.append("DATABASE_CONNECTION_STRING")
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in your .env file")
    
    # Start stale PR checker in a separate thread if Slack webhook is configured
    if SLACK_WEBHOOK_URL:
        checker_thread = threading.Thread(target=stale_pr_checker, daemon=True)
        checker_thread.start()
        logger.info("Started stale PR checker thread")
    else:
        logger.warning("SLACK_WEBHOOK_URL not set, stale PR notifications disabled")
    
    logger.info("Starting GitHub webhook server...")
    app.run(host='0.0.0.0', port=5001, debug=False)