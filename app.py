from flask import Flask, request, render_template, jsonify
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
app.config['TEMPLATES_AUTO_RELOAD'] = True

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
        
        # Extract repository and user info
        repo_data = data['repository']
        user_data = data['pull_request']['user']
        pr_data = data['pull_request']
        
        # Store in database
        repo_id = db.get_or_create_repository(repo_data)
        user_id = db.get_or_create_user(user_data)
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
        
        # Extract repository, user, PR, and review info
        repo_data = data['repository']
        user_data = data['review']['user']
        pr_data = data['pull_request']
        review_data = data['review']
        
        # Store in database
        repo_id = db.get_or_create_repository(repo_data)
        reviewer_id = db.get_or_create_user(user_data)
        pr_author_id = db.get_or_create_user(pr_data['user'])
        pr_id = db.get_or_create_pull_request(pr_data, repo_id, pr_author_id)
        review_id = db.add_pr_review(review_data, pr_id, reviewer_id)
        
        db.close()
        return review_id
    except Exception as e:
        logger.error(f"Error processing review: {str(e)}")
        return None

def process_review_comment(data):
    """
    Process pull request review comment and store in database
    """
    try:
        db = DatabaseHandler()
        
        # Extract repository, user, PR, and comment info
        repo_data = data['repository']
        user_data = data['comment']['user']
        pr_data = data['pull_request']
        comment_data = data['comment']
        
        # Store in database
        repo_id = db.get_or_create_repository(repo_data)
        commenter_id = db.get_or_create_user(user_data)
        pr_author_id = db.get_or_create_user(pr_data['user'])
        pr_id = db.get_or_create_pull_request(pr_data, repo_id, pr_author_id)
        
        # Check if this comment is associated with a review
        review_id = None
        if 'pull_request_review_id' in comment_data:
            # This is a review comment - need to find its review ID in our DB
            # In a real implementation, you'd store a mapping of GitHub review IDs to your DB IDs
            # For simplicity, we'll pass None here
            pass
        
        comment_id = db.add_review_comment(comment_data, pr_id, commenter_id, review_id)
        
        # Check if it contains a command and handle accordingly
        if comment_data.get('contains_command'):
            logger.info(f"Command detected in comment: {comment_data.get('command_type')}")
            # You could add specific command handling here
        
        db.close()
        return comment_id
    except Exception as e:
        logger.error(f"Error processing review comment: {str(e)}")
        return None

def check_stale_prs():
    """
    Check for stale PRs and send notifications
    """
    try:
        db = DatabaseHandler()
        newly_stale_pr_ids = db.check_for_stale_prs(STALE_PR_DAYS)
        
        if newly_stale_pr_ids:
            stale_prs = db.get_stale_prs()
            
            # Notify about stale PRs
            title = "🚨 Stale Pull Requests Detected"
            text = f"The following pull requests have been inactive for {STALE_PR_DAYS} days:"
            
            fields = []
            actions = []
            
            # Only include up to 10 PRs to avoid Slack message size limits
            for i, pr in enumerate(stale_prs[:10]):
                pr_id, pr_title, pr_number, pr_url, repo_name, username, created_at, last_activity = pr
                
                days_inactive = (datetime.utcnow() - last_activity).days
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

# Background task for checking stale PRs weekly
def stale_pr_checker():
    """Background thread to check for stale PRs on a schedule"""
    while True:
        logger.info("Running scheduled stale PR check")
        check_stale_prs()
        # Sleep for 1 day (86400 seconds)
        time.sleep(86400)

@app.route('/', methods=['GET'])
def home():
    """Home page with dashboard"""
    try:
        db = DatabaseHandler()
        metrics = db.get_pr_metrics()
        db.close()
        
        # Inject current year for the template
        current_year = datetime.now().year
        
        return render_template('dashboard.html', metrics=metrics, current_year=current_year)
    except Exception as e:
        logger.error(f"Error rendering dashboard: {str(e)}")
        return f"Error: {str(e)}", 500

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
        return 'Invalid signature', 400
    
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
                if action == 'opened':
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
                
                return 'PR processed', 200
                
        elif event_type == 'pull_request_review':
            review_id = process_review(data)
            
            # Send notification for requested changes
            if data['review']['state'] == 'changes_requested':
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
            
            return 'Review processed', 200
            
        elif event_type == 'pull_request_review_comment':
            comment_id = process_review_comment(data)
            return 'Comment processed', 200
            
        return 'Event received', 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return 'Error processing webhook', 500

@app.route('/stale', methods=['GET'])
def stale_prs():
    """
    Display stale pull requests
    """
    try:
        db = DatabaseHandler()
        stale_prs = db.get_stale_prs()
        
        # Get unique repository names for the filter
        repositories = set()
        for pr in stale_prs:
            repositories.add(pr[4])  # Repository name is at index 4
        
        db.close()
        
        return render_template(
            'stale_prs.html', 
            stale_prs=stale_prs, 
            repositories=sorted(repositories),
            stale_days=STALE_PR_DAYS,
            now=datetime.utcnow(),
            current_year=datetime.now().year
        )
    except Exception as e:
        logger.error(f"Error displaying stale PRs: {str(e)}")
        return f"Error: {str(e)}", 500

@app.route('/metrics', methods=['GET'])
def metrics_json():
    """
    Return metrics as JSON for API use
    """
    try:
        db = DatabaseHandler()
        metrics = db.get_pr_metrics()
        db.close()
        
        # Convert DB rows to dictionaries for JSON serialization
        result = {
            'pr_authors': [{'username': row[0], 'count': row[1]} for row in metrics['pr_authors']],
            'active_reviewers': [{'username': row[0], 'count': row[1]} for row in metrics['active_reviewers']],
            'command_users': [{'username': row[0], 'count': row[1]} for row in metrics['command_users']],
            'stale_pr_count': metrics['stale_pr_count']
        }
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Regular route that GitHub pings to check service status
@app.route('/', methods=['GET'])
def index():
    """
    Provide a simple status page
    """
    return render_template('dashboard.html')

if __name__ == '__main__':
    # Start stale PR checker in a separate thread
    checker_thread = threading.Thread(target=stale_pr_checker, daemon=True)
    checker_thread.start()
    
    # Verify environment variables
    if not SLACK_WEBHOOK_URL:
        raise ValueError("SLACK_WEBHOOK_URL is not set in .env file")
    if not GITHUB_SECRET:
        raise ValueError("GITHUB_WEBHOOK_SECRET is not set in .env file")
    
    logger.info("Starting server...")
    app.run(host='0.0.0.0', port=5001, debug=False)
