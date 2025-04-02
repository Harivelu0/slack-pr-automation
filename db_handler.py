import os
import logging
import pyodbc
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self):
        """Initialize database connection using Azure SQL"""
        try:
            # Get connection details from environment variables
            server = os.getenv('SQL_SERVER')
            database = os.getenv('SQL_DATABASE')
            username = os.getenv('SQL_USERNAME')
            password = os.getenv('SQL_PASSWORD')
            
            # Build connection string for Azure SQL
            conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
            
            # Connect to database
            self.conn = pyodbc.connect(conn_str)
            self.cursor = self.conn.cursor()
            logger.info("Successfully connected to Azure SQL database")
            
            # Initialize tables if they don't exist
            self._ensure_tables_exist()
            
        except Exception as e:
            logger.error(f"Error connecting to database: {str(e)}")
            # Instead of raising the error, set up a flag to indicate DB connection failed
            self.conn = None
            self.cursor = None
            self.connection_failed = True
            logger.warning("Using mock database functionality due to connection failure")
    
    def close(self):
        """Close the database connection"""
        if hasattr(self, 'conn') and self.conn:
            self.cursor.close()
            self.conn.close()
            logger.info("Database connection closed")
    
    def _ensure_tables_exist(self):
        """Create tables if they don't exist"""
        # Check if we have a valid connection
        if not hasattr(self, 'conn') or not self.conn:
            logger.warning("Cannot create tables without a database connection")
            return
            
        try:
            # Create repositories table
            self.cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'repositories')
            CREATE TABLE repositories (
                id INT IDENTITY(1,1) PRIMARY KEY,
                github_id INT UNIQUE,
                name NVARCHAR(255) NOT NULL,
                full_name NVARCHAR(255) NOT NULL,
                created_at DATETIME DEFAULT GETDATE()
            )
            ''')
            
            # Create users table
            self.cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'users')
            CREATE TABLE users (
                id INT IDENTITY(1,1) PRIMARY KEY,
                github_id INT UNIQUE,
                username NVARCHAR(255) NOT NULL,
                avatar_url NVARCHAR(255),
                created_at DATETIME DEFAULT GETDATE()
            )
            ''')
            
            # Create pull_requests table
            self.cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'pull_requests')
            CREATE TABLE pull_requests (
                id INT IDENTITY(1,1) PRIMARY KEY,
                github_id INT UNIQUE,
                repository_id INT,
                author_id INT,
                title NVARCHAR(1000) NOT NULL,
                number INT NOT NULL,
                state NVARCHAR(50) NOT NULL,
                html_url NVARCHAR(500) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                closed_at DATETIME NULL,
                merged_at DATETIME NULL,
                is_stale BIT DEFAULT 0,
                last_activity_at DATETIME NOT NULL,
                FOREIGN KEY (repository_id) REFERENCES repositories(id),
                FOREIGN KEY (author_id) REFERENCES users(id)
            )
            ''')
            
            # Create pr_reviews table
            self.cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'pr_reviews')
            CREATE TABLE pr_reviews (
                id INT IDENTITY(1,1) PRIMARY KEY,
                github_id INT UNIQUE,
                pull_request_id INT,
                reviewer_id INT,
                state NVARCHAR(50) NOT NULL,
                submitted_at DATETIME NOT NULL,
                FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id),
                FOREIGN KEY (reviewer_id) REFERENCES users(id)
            )
            ''')
            
            # Create review_comments table
            self.cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'review_comments')
            CREATE TABLE review_comments (
                id INT IDENTITY(1,1) PRIMARY KEY,
                github_id INT UNIQUE,
                review_id INT NULL,
                pull_request_id INT,
                author_id INT,
                body NVARCHAR(MAX) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                contains_command BIT DEFAULT 0,
                command_type NVARCHAR(50) NULL,
                FOREIGN KEY (review_id) REFERENCES pr_reviews(id),
                FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id),
                FOREIGN KEY (author_id) REFERENCES users(id)
            )
            ''')
            
            self.conn.commit()
            logger.info("Database tables verified/created successfully")
            
        except Exception as e:
            logger.error(f"Error creating tables: {str(e)}")
            self.conn.rollback()
    
    # Repository methods
    def get_or_create_repository(self, repo_data):
        """Get or create a repository record"""
        # Check if we have a valid connection
        if not hasattr(self, 'conn') or not self.conn:
            logger.warning("Database operation skipped due to missing connection")
            return None
            
        try:
            # Handle the case when repo_data is None
            if repo_data is None:
                logger.error("Repository data is None")
                return None
                
            github_id = repo_data.get('id')
            if github_id is None:
                logger.error("Repository github_id is missing")
                return None
                
            # Check if repository exists
            self.cursor.execute(
                "SELECT id FROM repositories WHERE github_id = ?", 
                (github_id,)
            )
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            
            # Repository doesn't exist, create it
            name = repo_data.get('name', 'unknown')
            full_name = repo_data.get('full_name', 'unknown/unknown')
            
            self.cursor.execute(
                "INSERT INTO repositories (github_id, name, full_name) VALUES (?, ?, ?)", 
                (github_id, name, full_name)
            )
            self.conn.commit()
            
            # Get the new ID
            self.cursor.execute("SELECT @@IDENTITY")
            return self.cursor.fetchone()[0]
            
        except Exception as e:
            logger.error(f"Error in get_or_create_repository: {str(e)}")
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return None
    
    # User methods
    def get_or_create_user(self, user_data):
        """Get or create a user record"""
        # Check if we have a valid connection
        if not hasattr(self, 'conn') or not self.conn:
            logger.warning("Database operation skipped due to missing connection")
            return None
            
        try:
            # Handle the case when user_data is None
            if user_data is None:
                logger.error("User data is None")
                return None
                
            github_id = user_data.get('id')
            if github_id is None:
                logger.error("User github_id is missing")
                return None
                
            # Check if user exists
            self.cursor.execute(
                "SELECT id FROM users WHERE github_id = ?", 
                (github_id,)
            )
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            
            # User doesn't exist, create it
            username = user_data.get('login', 'unknown')
            avatar_url = user_data.get('avatar_url')
            
            self.cursor.execute(
                "INSERT INTO users (github_id, username, avatar_url) VALUES (?, ?, ?)", 
                (github_id, username, avatar_url)
            )
            self.conn.commit()
            
            # Get the new ID
            self.cursor.execute("SELECT @@IDENTITY")
            return self.cursor.fetchone()[0]
            
        except Exception as e:
            logger.error(f"Error in get_or_create_user: {str(e)}")
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return None
    
    # Pull Request methods
    def get_or_create_pull_request(self, pr_data, repository_id, author_id):
        """Get or create a pull request record"""
        # Check if we have a valid connection
        if not hasattr(self, 'conn') or not self.conn:
            logger.warning("Database operation skipped due to missing connection")
            return None
            
        try:
            # Handle the case when pr_data is None or IDs are None
            if pr_data is None:
                logger.error("PR data is None")
                return None
                
            if repository_id is None or author_id is None:
                logger.error(f"Missing required IDs: repo_id={repository_id}, author_id={author_id}")
                return None
                
            github_id = pr_data.get('id')
            if github_id is None:
                logger.error("PR github_id is missing")
                return None
                
            # Check if PR exists
            self.cursor.execute(
                "SELECT id FROM pull_requests WHERE github_id = ?", 
                (github_id,)
            )
            result = self.cursor.fetchone()
            
            # Ensure timestamps are properly formatted
            created_at = pr_data.get('created_at')
            updated_at = pr_data.get('updated_at')
            closed_at = pr_data.get('closed_at')
            merged_at = pr_data.get('merged_at')
            
            # Extract other data with defaults
            title = pr_data.get('title', 'Untitled PR')
            number = pr_data.get('number', 0)
            state = pr_data.get('state', 'open')
            html_url = pr_data.get('html_url', '')
            
            if result:
                # PR exists, update it
                pr_id = result[0]
                self.cursor.execute(
                    """UPDATE pull_requests 
                       SET title = ?, 
                           state = ?, 
                           updated_at = ?, 
                           closed_at = ?, 
                           merged_at = ?,
                           last_activity_at = ?
                       WHERE id = ?""", 
                    (title, state, updated_at, closed_at, merged_at, updated_at, pr_id)
                )
                self.conn.commit()
                return pr_id
            
            # PR doesn't exist, create it
            self.cursor.execute(
                """INSERT INTO pull_requests 
                   (github_id, repository_id, author_id, title, number, state, html_url, 
                    created_at, updated_at, closed_at, merged_at, last_activity_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                (github_id, repository_id, author_id, title, number, state, html_url, 
                 created_at, updated_at, closed_at, merged_at, updated_at)
            )
            self.conn.commit()
            
            # Get the new ID
            self.cursor.execute("SELECT @@IDENTITY")
            return self.cursor.fetchone()[0]
            
        except Exception as e:
            logger.error(f"Error in get_or_create_pull_request: {str(e)}")
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return None
    
    # PR Review methods
    def add_pr_review(self, review_data, pull_request_id, reviewer_id):
        """Add a new PR review"""
        # Check if we have a valid connection
        if not hasattr(self, 'conn') or not self.conn:
            logger.warning("Database operation skipped due to missing connection")
            return None
            
        try:
            # Handle missing data
            if review_data is None or pull_request_id is None or reviewer_id is None:
                logger.error("Missing required data for PR review")
                return None
                
            github_id = review_data.get('id')
            if github_id is None:
                logger.error("Review github_id is missing")
                return None
                
            # Get state and submitted_at with defaults
            state = review_data.get('state', 'COMMENTED')
            submitted_at = review_data.get('submitted_at', datetime.now().isoformat())
            
            # Check if review exists
            self.cursor.execute(
                "SELECT id FROM pr_reviews WHERE github_id = ?", 
                (github_id,)
            )
            result = self.cursor.fetchone()
            
            if result:
                # Review exists, update it
                review_id = result[0]
                self.cursor.execute(
                    "UPDATE pr_reviews SET state = ? WHERE id = ?", 
                    (state, review_id)
                )
                self.conn.commit()
                
                # Update last activity on PR
                self.cursor.execute(
                    "UPDATE pull_requests SET last_activity_at = ?, is_stale = 0 WHERE id = ?", 
                    (submitted_at, pull_request_id)
                )
                self.conn.commit()
                return review_id
            
            # Review doesn't exist, create it
            self.cursor.execute(
                """INSERT INTO pr_reviews 
                   (github_id, pull_request_id, reviewer_id, state, submitted_at) 
                   VALUES (?, ?, ?, ?, ?)""", 
                (github_id, pull_request_id, reviewer_id, state, submitted_at)
            )
            self.conn.commit()
            
            # Get the new ID
            self.cursor.execute("SELECT @@IDENTITY")
            review_id = self.cursor.fetchone()[0]
            
            # Update last activity on PR
            self.cursor.execute(
                "UPDATE pull_requests SET last_activity_at = ?, is_stale = 0 WHERE id = ?", 
                (submitted_at, pull_request_id)
            )
            self.conn.commit()
            
            return review_id
            
        except Exception as e:
            logger.error(f"Error in add_pr_review: {str(e)}")
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return None
    
    # Review Comment methods
    def add_review_comment(self, comment_data, pull_request_id, author_id, review_id=None):
        """Add a review comment"""
        # Check if we have a valid connection
        if not hasattr(self, 'conn') or not self.conn:
            logger.warning("Database operation skipped due to missing connection")
            return None
            
        try:
            # Handle missing data
            if comment_data is None or pull_request_id is None or author_id is None:
                logger.error("Missing required data for review comment")
                return None
                
            github_id = comment_data.get('id')
            if github_id is None:
                logger.error("Comment github_id is missing")
                return None
                
            # Get data with defaults
            body = comment_data.get('body', '')
            created_at = comment_data.get('created_at', datetime.now().isoformat())
            updated_at = comment_data.get('updated_at', datetime.now().isoformat())
            
            # Check for commands in comment (simplified)
            contains_command = 0
            command_type = None
            
            # Simple command detection - check for common commands
            command_keywords = ['LGTM', 'APPROVE', 'REQUEST CHANGES', 'NEED REVIEW']
            for cmd in command_keywords:
                if cmd in body.upper():
                    contains_command = 1
                    command_type = cmd
                    break
            
            # Check if comment exists
            self.cursor.execute(
                "SELECT id FROM review_comments WHERE github_id = ?", 
                (github_id,)
            )
            result = self.cursor.fetchone()
            
            if result:
                # Comment exists, update it
                comment_id = result[0]
                self.cursor.execute(
                    """UPDATE review_comments 
                       SET body = ?, updated_at = ?, contains_command = ?, command_type = ? 
                       WHERE id = ?""", 
                    (body, updated_at, contains_command, command_type, comment_id)
                )
                self.conn.commit()
                
                # Update last activity on PR
                self.cursor.execute(
                    "UPDATE pull_requests SET last_activity_at = ?, is_stale = 0 WHERE id = ?", 
                    (updated_at, pull_request_id)
                )
                self.conn.commit()
                return comment_id
            
            # Comment doesn't exist, create it
            self.cursor.execute(
                """INSERT INTO review_comments 
                   (github_id, review_id, pull_request_id, author_id, body, created_at, updated_at, contains_command, command_type) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                (github_id, review_id, pull_request_id, author_id, body, created_at, updated_at, contains_command, command_type)
            )
            self.conn.commit()
            
            # Get the new ID
            self.cursor.execute("SELECT @@IDENTITY")
            comment_id = self.cursor.fetchone()[0]
            
            # Update last activity on PR
            self.cursor.execute(
                "UPDATE pull_requests SET last_activity_at = ?, is_stale = 0 WHERE id = ?", 
                (updated_at, pull_request_id)
            )
            self.conn.commit()
            
            return comment_id
            
        except Exception as e:
            logger.error(f"Error in add_review_comment: {str(e)}")
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return None
    
    # Stale PR methods
    def check_for_stale_prs(self, days_threshold=7):
        """Mark PRs as stale if they haven't had activity in the specified number of days"""
        # Check if we have a valid connection
        if not hasattr(self, 'conn') or not self.conn:
            logger.warning("Database operation skipped due to missing connection")
            return []
            
        try:
            stale_date = (datetime.now() - timedelta(days=days_threshold))
            
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
                    "UPDATE pull_requests SET is_stale = 1 WHERE id = ?", 
                    (pr_id,)
                )
                newly_stale_pr_ids.append(pr_id)
            
            self.conn.commit()
            return newly_stale_pr_ids
            
        except Exception as e:
            logger.error(f"Error in check_for_stale_prs: {str(e)}")
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return []
    
    def get_stale_prs(self):
        """Get all currently stale PRs"""
        # Check if we have a valid connection
        if not hasattr(self, 'conn') or not self.conn:
            logger.warning("Database operation skipped due to missing connection")
            return []
            
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
            return []