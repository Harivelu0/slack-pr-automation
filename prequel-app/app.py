from flask import Flask, request, jsonify
import logging
import threading
import time
import os
from datetime import datetime
from dotenv import load_dotenv
from github_handler import (
    verify_github_webhook,
    process_pull_request,
    process_review,
    process_review_comment
)
from slack_notifier import send_slack_notification, check_stale_prs

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

# Background task for checking stale PRs
def stale_pr_checker():
    """Background thread to check for stale PRs on a schedule"""
    while True:
        logger.info("Running scheduled stale PR check")
        check_stale_prs(STALE_PR_DAYS)
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
    if not verify_github_webhook(request, GITHUB_SECRET):
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
                    
                    send_slack_notification(SLACK_WEBHOOK_URL, title, text, fields, actions)
                
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
                
                send_slack_notification(SLACK_WEBHOOK_URL, title, text, fields, actions)
            
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