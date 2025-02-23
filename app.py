from flask import Flask, request
import requests
import os
import hmac
import hashlib
import logging
import json
from dotenv import load_dotenv

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

def send_slack_notification(pr_data):
    """
    Send notification to Slack channel about new PR
    """
    try:
        logger.debug(f"Processing PR data: {json.dumps(pr_data, indent=2)}")
        pr = pr_data['pull_request']
        repo = pr_data['repository']
        
        message = {
            "text": f"New Pull Request: {pr['title']}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🔔 New Pull Request Created"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Repository:*\n{repo['full_name']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Created by:*\n{pr['user']['login']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Title:* {pr['title']}\n{pr.get('body', 'No description provided.')}"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "View Pull Request"
                            },
                            "url": pr['html_url']
                        }
                    ]
                }
            ]
        }
        
        logger.debug("Sending notification to Slack")
        response = requests.post(SLACK_WEBHOOK_URL, json=message)
        logger.debug(f"Slack API Response: {response.status_code} - {response.text}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error sending Slack notification: {str(e)}")
        return False

@app.route('/', methods=['GET', 'POST'])
def handle_webhook():
    """
    Handle GitHub webhook events
    """
    if request.method == 'GET':
        return 'GitHub webhook server is running!', 200
        
    logger.info("Received webhook request")
    logger.debug(f"Request Headers: {dict(request.headers)}")
    logger.debug(f"Request Data Length: {len(request.get_data())} bytes")
    
    # Print environment variables (without secrets)
    logger.debug(f"SLACK_WEBHOOK_URL configured: {'Yes' if SLACK_WEBHOOK_URL else 'No'}")
    logger.debug(f"GITHUB_SECRET configured: {'Yes' if GITHUB_SECRET else 'No'}")
    
    # Verify webhook signature
    if not verify_github_webhook(request):
        logger.error("Webhook verification failed")
        return 'Invalid signature', 400
    
    try:
        data = request.get_json()
        logger.debug(f"Parsed JSON data: {json.dumps(data, indent=2)}")
    except Exception as e:
        logger.error(f"Failed to parse JSON: {str(e)}")
        return 'Invalid JSON', 400
    
    # Check if it's a PR event
    event_type = request.headers.get('X-GitHub-Event')
    logger.info(f"Event type: {event_type}")
    
    if event_type == 'pull_request' and data.get('action') == 'opened':
        logger.info("Processing new PR event")
        success = send_slack_notification(data)
        if success:
            return 'Notification sent successfully', 200
        else:
            return 'Failed to send notification', 500
    
    return 'Event received', 200

if __name__ == '__main__':
    # Verify environment variables
    if not SLACK_WEBHOOK_URL:
        raise ValueError("SLACK_WEBHOOK_URL is not set in .env file")
    if not GITHUB_SECRET:
        raise ValueError("GITHUB_WEBHOOK_SECRET is not set in .env file")
    
    logger.info("Starting server...")
    logger.info("Webhook URL should be: <your-ngrok-url>")
    app.run(host='127.0.0.1', port=5000, debug=False)
