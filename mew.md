files, each with a specific responsibility:

app.py: The main application file containing:

Flask app initialization and configuration
Route handlers for the API endpoints
The main entry point of the application
The background thread for checking stale PRs


github_handler.py: All GitHub-related functionality:

Webhook signature verification
Functions to process different types of GitHub events (PRs, reviews, comments)
Database interactions related to GitHub data


slack_notifier.py: All Slack-related functionality:

Function to send notifications to Slack
Logic for checking and notifying about stale PRs