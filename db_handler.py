import os
import sqlite3
import logging
from datetime import datetime, timedelta
import re

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self):
    # Get connection details from environment variables
        server = os.getenv('SQL_SERVER')
        database = os.getenv('SQL_DATABASE')
        username = os.getenv('SQL_USERNAME')
        password = os.getenv('SQL_PASSWORD')
        
        # Build connection string
        conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
        
        try:
            # Connect to database
            self.conn = pyodbc.connect(conn_str)
            self.cursor = self.conn.cursor()
            logger.info("Successfully connected to database")
        except Exception as e:
            logger.error(f"Error connecting to database: {str(e)}")
            raise
    
    def close(self):
        """Close the database connection"""
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def _initialize_sqlite_db(self):
        """Create tables in SQLite if they don't exist"""
        # Simplified schema for SQLite
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY,
            github_id INTEGER UNIQUE,
            name TEXT NOT NULL,
            full_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            github_id INTEGER UNIQUE,
            username TEXT NOT NULL,
            avatar_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS pull_requests (
            id INTEGER PRIMARY KEY,
            github_id INTEGER UNIQUE,
            repository_id INTEGER,
            author_id INTEGER,
            title TEXT NOT NULL,
            number INTEGER NOT NULL,
            state TEXT NOT NULL,
            html_url TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            closed_at TIMESTAMP,
            merged_at TIMESTAMP,
            is_stale INTEGER DEFAULT 0,
            last_activity_at TIMESTAMP NOT NULL,
            FOREIGN KEY (repository_id) REFERENCES repositories(id),
            FOREIGN KEY (author_id) REFERENCES users(id)
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS pr_reviews (
            id INTEGER PRIMARY KEY,
            github_id INTEGER UNIQUE,
            pull_request_id INTEGER,
            reviewer_id INTEGER,
            state TEXT NOT NULL,
            submitted_at TIMESTAMP NOT NULL,
            FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id),
            FOREIGN KEY (reviewer_id) REFERENCES users(id)
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS review_comments (
            id INTEGER PRIMARY KEY,
            github_id INTEGER UNIQUE,
            review_id INTEGER,
            pull_request_id INTEGER,
            author_id INTEGER,
            body TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            contains_command INTEGER DEFAULT 0,
            command_type TEXT,
            FOREIGN KEY (review_id) REFERENCES pr_reviews(id),
            FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id),
            FOREIGN KEY (author_id) REFERENCES users(id)
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS stale_pr_history (
            id INTEGER PRIMARY KEY,
            pull_request_id INTEGER,
            marked_stale_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            marked_active_at TIMESTAMP,
            notification_sent INTEGER DEFAULT 0,
            FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id)
        )
        ''')
        
        # Add some test data if the database is empty
        self.cursor.execute("SELECT COUNT(*) FROM repositories")
        count = self.cursor.fetchone()[0]
        
        if count == 0:
            self._add_test_data()
        
        self.conn.commit()
    
    def _add_test_data(self):
        """Add test data to the database"""
        # Add test repositories
        repos = [
            (100001, "frontend", "Shetchuko/frontend"),
            (100002, "backend", "Shetchuko/backend"),
            (100003, "api", "Shetchuko/api")
        ]
        for repo in repos:
            self.cursor.execute(
                "INSERT INTO repositories (github_id, name, full_name) VALUES (?, ?, ?)",
                repo
            )
        
        # Add test users
        users = [
            (200001, "alice", "https://example.com/alice.png"),
            (200002, "bob", "https://example.com/bob.png"),
            (200003, "charlie", "https://example.com/charlie.png")
        ]
        for user in users:
            self.cursor.execute(
                "INSERT INTO users (github_id, username, avatar_url) VALUES (?, ?, ?)",
                user
            )
        
        # Add test PRs
        now = datetime.now().isoformat()
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        month_ago = (datetime.now() - timedelta(days=30)).isoformat()
        
        prs = [
            # Active PRs
            (300001, 1, 1, "Feature: Add login page", 1, "open", "https://github.com/Shetchuko/frontend/pull/1", 
             week_ago, now, None, None, 0, now),
            (300002, 1, 2, "Feature: Add signup flow", 2, "open", "https://github.com/Shetchuko/frontend/pull/2", 
             week_ago, now, None, None, 0, now),
            (300003, 2, 3, "Fix: API authentication", 3, "open", "https://github.com/Shetchuko/backend/pull/3", 
             week_ago, now, None, None, 0, now),
            
            # Stale PRs
            (300004, 3, 1, "Feature: Add settings page", 4, "open", "https://github.com/Shetchuko/api/pull/4", 
             month_ago, week_ago, None, None, 1, week_ago),
            (300005, 2, 2, "Fix: Database migration", 5, "open", "https://github.com/Shetchuko/backend/pull/5", 
             month_ago, week_ago, None, None, 1, week_ago)
        ]
        
        for pr in prs:
            self.cursor.execute(
                """INSERT INTO pull_requests 
                (github_id, repository_id, author_id, title, number, state, html_url, 
                created_at, updated_at, closed_at, merged_at, is_stale, last_activity_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                pr
            )
        
        # Add test reviews
        reviews = [
            (400001, 1, 2, "APPROVED", now),
            (400002, 2, 3, "CHANGES_REQUESTED", week_ago),
            (400003, 3, 1, "COMMENTED", week_ago)
        ]
        
        for review in reviews:
            self.cursor.execute(
                "INSERT INTO pr_reviews (github_id, pull_request_id, reviewer_id, state, submitted_at) VALUES (?, ?, ?, ?, ?)",
                review
            )
        
        # Add test comments with commands
        comments = [
            (500001, None, 1, 2, "LGTM: This looks good to me!", week_ago, week_ago, 1, "LGTM"),
            (500002, None, 2, 3, "APPROVE: Ready to merge", week_ago, week_ago, 1, "APPROVE"),
            (500003, None, 3, 1, "Need to fix the tests", week_ago, week_ago, 0, None)
        ]
        
        for comment in comments:
            self.cursor.execute(
                """INSERT INTO review_comments 
                (github_id, review_id, pull_request_id, author_id, body, created_at, updated_at, contains_command, command_type) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                comment
            )
        
        self.conn.commit()
    
    # Repository methods
    def get_or_create_repository(self, repo_data):
        """Get or create a repository record"""
        try:
            github_id = repo_data['id']
            self.cursor.execute(
                """SELECT id FROM repositories WHERE github_id = ?""", 
                (github_id,)
            )
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            
            # Repository doesn't exist, create it
            self.cursor.execute(
                """INSERT INTO repositories (github_id, name, full_name) 
                   VALUES (?, ?, ?)""", 
                (github_id, repo_data['name'], repo_data['full_name'])
            )
            self.conn.commit()
            
            # Get the new ID
            self.cursor.execute("SELECT last_insert_rowid()")
            return self.cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error in get_or_create_repository: {str(e)}")
            self.conn.rollback()
            raise
    
    # User methods
    def get_or_create_user(self, user_data):
        """Get or create a user record"""
        try:
            github_id = user_data['id']
            self.cursor.execute(
                """SELECT id FROM users WHERE github_id = ?""", 
                (github_id,)
            )
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            
            # User doesn't exist, create it
            self.cursor.execute(
                """INSERT INTO users (github_id, username, avatar_url) 
                   VALUES (?, ?, ?)""", 
                (github_id, user_data['login'], user_data.get('avatar_url'))
            )
            self.conn.commit()
            
            # Get the new ID
            self.cursor.execute("SELECT last_insert_rowid()")
            return self.cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error in get_or_create_user: {str(e)}")
            self.conn.rollback()
            raise
    
    # Pull Request methods
    def get_or_create_pull_request(self, pr_data, repository_id, author_id):
        """Get or create a pull request record"""
        try:
            github_id = pr_data['id']
            self.cursor.execute(
                """SELECT id FROM pull_requests WHERE github_id = ?""", 
                (github_id,)
            )
            result = self.cursor.fetchone()
            
            if result:
                # Update the PR
                self.cursor.execute(
                    """UPDATE pull_requests 
                       SET state = ?, 
                           updated_at = ?, 
                           closed_at = ?, 
                           merged_at = ?,
                           last_activity_at = ?
                       WHERE id = ?""", 
                    (
                        pr_data['state'],
                        pr_data['updated_at'],
                        pr_data.get('closed_at'),
                        pr_data.get('merged_at'),
                        pr_data['updated_at'],
                        result[0]
                    )
                )
                self.conn.commit()
                return result[0]
            
            # PR doesn't exist, create it
            self.cursor.execute(
                """INSERT INTO pull_requests 
                   (github_id, repository_id, author_id, title, number, state, html_url, 
                    created_at, updated_at, closed_at, merged_at, last_activity_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                (
                    github_id, 
                    repository_id, 
                    author_id, 
                    pr_data['title'], 
                    pr_data['number'], 
                    pr_data['state'], 
                    pr_data['html_url'], 
                    pr_data['created_at'], 
                    pr_data['updated_at'], 
                    pr_data.get('closed_at'), 
                    pr_data.get('merged_at'),
                    pr_data['updated_at']
                )
            )
            self.conn.commit()
            
            # Get the new ID
            self.cursor.execute("SELECT last_insert_rowid()")
            return self.cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error in get_or_create_pull_request: {str(e)}")
            self.conn.rollback()
            raise
    
    # PR Review methods
    def add_pr_review(self, review_data, pull_request_id, reviewer_id):
        """Add a new PR review"""
        try:
            github_id = review_data['id']
            self.cursor.execute(
                """SELECT id FROM pr_reviews WHERE github_id = ?""", 
                (github_id,)
            )
            result = self.cursor.fetchone()
            
            if result:
                # Review already exists, update it
                self.cursor.execute(
                    """UPDATE pr_reviews 
                       SET state = ? 
                       WHERE id = ?""", 
                    (review_data['state'], result[0])
                )
                self.conn.commit()
                
                # Update last activity on PR
                self.cursor.execute(
                    """UPDATE pull_requests 
                       SET last_activity_at = ?, is_stale = 0 
                       WHERE id = ?""", 
                    (review_data['submitted_at'], pull_request_id)
                )
                self.conn.commit()
                return result[0]
            
            # Review doesn't exist, create it
            self.cursor.execute(
                """INSERT INTO pr_reviews (github_id, pull_request_id, reviewer_id, state, submitted_at) 
                   VALUES (?, ?, ?, ?, ?)""", 
                (
                    github_id, 
                    pull_request_id, 
                    reviewer_id, 
                    review_data['state'], 
                    review_data['submitted_at']
                )
            )
            self.conn.commit()
            
            # Get the new ID
            self.cursor.execute("SELECT last_insert_rowid()")
            review_id = self.cursor.fetchone()[0]
            
            # Update last activity on PR
            self.cursor.execute(
                """UPDATE pull_requests 
                   SET last_activity_at = ?, is_stale = 0 
                   WHERE id = ?""", 
                (review_data['submitted_at'], pull_request_id)
            )
            self.conn.commit()
            return review_id
        except Exception as e:
            logger.error(f"Error in add_pr_review: {str(e)}")
            self.conn.rollback()
            raise
    
    # Review Comment methods with command detection
    def add_review_comment(self, comment_data, pull_request_id, author_id, review_id=None):
        """Add a review comment and detect commands"""
        try:
            github_id = comment_data['id']
            body = comment_data['body']
            
            # Check for commands in the comment
            contains_command = False
            command_type = None
            
            # Define regex patterns for common PR commands
            command_patterns = {
                'LGTM': r'\bLGTM\b',
                'APPROVE': r'\bAPPROVE\b',
                'REQUEST_CHANGES': r'\bREQUEST[_ ]CHANGES\b',
                'NEED_REVIEW': r'\bNEED[_ ]REVIEW\b',
                'FIX_IT': r'\bFIX[_ ]IT\b',
                'RETRY': r'\bRETRY\b',
            }
            
            for cmd, pattern in command_patterns.items():
                if re.search(pattern, body, re.IGNORECASE):
                    contains_command = True
                    command_type = cmd
                    break
            
            self.cursor.execute(
                """SELECT id FROM review_comments WHERE github_id = ?""", 
                (github_id,)
            )
            result = self.cursor.fetchone()
            
            if result:
                # Comment already exists, update it
                self.cursor.execute(
                    """UPDATE review_comments 
                       SET body = ?, updated_at = ?, contains_command = ?, command_type = ? 
                       WHERE id = ?""", 
                    (body, comment_data['updated_at'], contains_command, command_type, result[0])
                )
                self.conn.commit()
                
                # Update last activity on PR
                self.cursor.execute(
                    """UPDATE pull_requests 
                       SET last_activity_at = ?, is_stale = 0 
                       WHERE id = ?""", 
                    (comment_data['updated_at'], pull_request_id)
                )
                self.conn.commit()
                return result[0]
            
            # Comment doesn't exist, create it
            self.cursor.execute(
                """INSERT INTO review_comments 
                   (github_id, review_id, pull_request_id, author_id, body, created_at, updated_at, contains_command, command_type) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                (
                    github_id, 
                    review_id, 
                    pull_request_id, 
                    author_id, 
                    body, 
                    comment_data['created_at'], 
                    comment_data['updated_at'],
                    1 if contains_command else 0,
                    command_type
                )
            )
            self.conn.commit()
            
            # Get the new ID
            self.cursor.execute("SELECT last_insert_rowid()")
            comment_id = self.cursor.fetchone()[0]
            
            # Update last activity on PR
            self.cursor.execute(
                """UPDATE pull_requests 
                   SET last_activity_at = ?, is_stale = 0 
                   WHERE id = ?""", 
                (comment_data['updated_at'], pull_request_id)
            )
            self.conn.commit()
            return comment_id
        except Exception as e:
            logger.error(f"Error in add_review_comment: {str(e)}")
            self.conn.rollback()
            raise
    
    # Stale PR methods
    def check_for_stale_prs(self, days_threshold=7):
        """Mark PRs as stale if they haven't had activity in the specified number of days"""
        try:
            stale_date = (datetime.now() - timedelta(days=days_threshold)).isoformat()
            
            # Find PRs that have become stale
            self.cursor.execute(
                """SELECT id 
                   FROM pull_requests 
                   WHERE state = 'open' 
                   AND is_stale = 0 
                   AND last_activity_at < ? 
                   AND (closed_at IS NULL AND merged_at IS NULL)""", 
                (stale_date,)
            )
            
            newly_stale_prs = self.cursor.fetchall()
            newly_stale_pr_ids = []
            
            # Mark PRs as stale
            for row in newly_stale_prs:
                pr_id = row[0]
                self.cursor.execute(
                    """UPDATE pull_requests SET is_stale = 1 WHERE id = ?""", 
                    (pr_id,)
                )
                
                # Add to stale PR history
                self.cursor.execute(
                    """INSERT INTO stale_pr_history (pull_request_id) VALUES (?)""", 
                    (pr_id,)
                )
                
                newly_stale_pr_ids.append(pr_id)
            
            self.conn.commit()
            return newly_stale_pr_ids
        except Exception as e:
            logger.error(f"Error in check_for_stale_prs: {str(e)}")
            self.conn.rollback()
            raise
    
    def get_stale_prs(self):
        """Get all currently stale PRs"""
        try:
            self.cursor.execute(
                """SELECT pr.id, pr.title, pr.number, pr.html_url, repo.full_name, u.username,
                          pr.created_at, pr.last_activity_at
                   FROM pull_requests pr
                   JOIN repositories repo ON pr.repository_id = repo.id
                   JOIN users u ON pr.author_id = u.id
                   WHERE pr.is_stale = 1
                   AND pr.state = 'open'
                   ORDER BY pr.last_activity_at ASC"""
            )
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"Error in get_stale_prs: {str(e)}")
            raise
    
    # Metrics methods for frontend
    def get_pr_metrics(self):
        """Get metrics for the frontend dashboard"""
        try:
            # Get PR authors count
            self.cursor.execute(
                """SELECT u.username, COUNT(pr.id) as pr_count
                   FROM users u
                   JOIN pull_requests pr ON u.id = pr.author_id
                   GROUP BY u.username
                   ORDER BY pr_count DESC"""
            )
            pr_authors = self.cursor.fetchall()
            
            # Get active reviewers
            self.cursor.execute(
                """SELECT u.username, COUNT(rv.id) as review_count
                   FROM users u
                   JOIN pr_reviews rv ON u.id = rv.reviewer_id
                   GROUP BY u.username
                   ORDER BY review_count DESC"""
            )
            active_reviewers = self.cursor.fetchall()
            
            # Get command users
            self.cursor.execute(
                """SELECT u.username, COUNT(rc.id) as command_count
                   FROM users u
                   JOIN review_comments rc ON u.id = rc.author_id
                   WHERE rc.contains_command = 1
                   GROUP BY u.username
                   ORDER BY command_count DESC"""
            )
            command_users = self.cursor.fetchall()
            
            # Get stale PR count
            self.cursor.execute(
                """SELECT COUNT(id) FROM pull_requests WHERE is_stale = 1 AND state = 'open'"""
            )
            stale_pr_count = self.cursor.fetchone()[0]
            
            return {
                'pr_authors': pr_authors,
                'active_reviewers': active_reviewers,
                'command_users': command_users,
                'stale_pr_count': stale_pr_count
            }
        except Exception as e:
            logger.error(f"Error in get_pr_metrics: {str(e)}")
            raise