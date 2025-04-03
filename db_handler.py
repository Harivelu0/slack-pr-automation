import os
import logging
from datetime import datetime, timedelta
import re

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define pyodbc at the module level
pyodbc = None

try:
    import pyodbc
    logger.info("Successfully imported pyodbc")
except ImportError as e:
    logger.error(f"Failed to import pyodbc: {str(e)}")
    # Temporary fallback to allow debugging
    class MockPyodbc:
        def connect(self, *args, **kwargs):
            logger.error("Using mock pyodbc connection")
            return None
    pyodbc = MockPyodbc()

class DatabaseHandler:
    
    def __init__(self):
        """Initialize database connection using environment variables"""
        try:
            # Import modules
            import os
            from dotenv import load_dotenv
            
            # Load environment variables from .env file
            load_dotenv()
            
            # Get credentials from environment variables with no defaults
            server = os.getenv("SQL_SERVER")
            database = os.getenv("SQL_DATABASE")
            username = os.getenv("SQL_USERNAME")
            password = os.getenv("SQL_PASSWORD")
            
            # Check if any required environment variables are missing
            missing_vars = []
            if not server: missing_vars.append("SQL_SERVER")
            if not database: missing_vars.append("SQL_DATABASE")
            if not username: missing_vars.append("SQL_USERNAME")
            if not password: missing_vars.append("SQL_PASSWORD")
            
            if missing_vars:
                raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
            
            logger.debug(f"Using database: {database} on server: {server}")
            
            # Build connection string
            conn_str = (
                f"Driver={{ODBC Driver 17 for SQL Server}};"
                f"Server=tcp:{server},1433;"
                f"Database={database};"
                f"Uid={username};"
                f"Pwd={password};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout=30;"
            )
            
            logger.debug(f"Attempting to connect to database")
            
            # Connect to database
            self.conn = pyodbc.connect(conn_str)
            self.cursor = self.conn.cursor()
            logger.info(f"Successfully connected to Azure SQL database at {server}")
            
            # Initialize tables if they don't exist
            self._ensure_tables_exist()
            
        except ValueError as e:
            # Handle missing environment variables
            logger.error(f"Environment variable error: {str(e)}")
            self.conn = None
            self.cursor = None
            self.connection_failed = True
            logger.warning("Using mock database functionality due to missing environment variables")
        except Exception as e:
            # Handle other errors
            logger.error(f"Error connecting to database: {str(e)}")
            self.conn = None
            self.cursor = None
            self.connection_failed = True
            logger.warning("Using mock database functionality due to connection failure")
    
    def close(self):
        """Close the database connection"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def _ensure_tables_exist(self):
        """Create tables if they don't exist in the Azure SQL database"""
        try:
            # Check if the repositories table exists
            self.cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[repositories]') AND type in (N'U'))
            BEGIN
                CREATE TABLE repositories (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    github_id BIGINT UNIQUE,
                    name NVARCHAR(255) NOT NULL,
                    full_name NVARCHAR(255) NOT NULL,
                    created_at DATETIME DEFAULT GETDATE()
                )
            END
            """)
            
            # Check if the users table exists
            self.cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[users]') AND type in (N'U'))
            BEGIN
                CREATE TABLE users (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    github_id BIGINT UNIQUE,
                    username NVARCHAR(255) NOT NULL,
                    avatar_url NVARCHAR(255),
                    created_at DATETIME DEFAULT GETDATE()
                )
            END
            """)
            
            # Check if the pull_requests table exists
            self.cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[pull_requests]') AND type in (N'U'))
            BEGIN
                CREATE TABLE pull_requests (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    github_id BIGINT UNIQUE,
                    repository_id INT,
                    author_id INT,
                    title NVARCHAR(255) NOT NULL,
                    number INT NOT NULL,
                    state NVARCHAR(50) NOT NULL,
                    html_url NVARCHAR(255) NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    closed_at DATETIME NULL,
                    merged_at DATETIME NULL,
                    is_stale BIT DEFAULT 0,
                    last_activity_at DATETIME NOT NULL,
                    FOREIGN KEY (repository_id) REFERENCES repositories(id),
                    FOREIGN KEY (author_id) REFERENCES users(id)
                )
            END
            """)
            
            # Check if the pr_reviews table exists
            self.cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[pr_reviews]') AND type in (N'U'))
            BEGIN
                CREATE TABLE pr_reviews (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    github_id BIGINT UNIQUE,
                    pull_request_id INT,
                    reviewer_id INT,
                    state NVARCHAR(50) NOT NULL,
                    submitted_at DATETIME NOT NULL,
                    FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id),
                    FOREIGN KEY (reviewer_id) REFERENCES users(id)
                )
            END
            """)
            
            # Check if the review_comments table exists
            self.cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[review_comments]') AND type in (N'U'))
            BEGIN
                CREATE TABLE review_comments (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    github_id BIGINT UNIQUE,
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
            END
            """)
            
            # Check if the stale_pr_history table exists
            self.cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[stale_pr_history]') AND type in (N'U'))
            BEGIN
                CREATE TABLE stale_pr_history (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    pull_request_id INT,
                    marked_stale_at DATETIME DEFAULT GETDATE(),
                    marked_active_at DATETIME NULL,
                    notification_sent BIT DEFAULT 0,
                    FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id)
                )
            END
            """)
            
            self.conn.commit()
            logger.info("Database tables initialized successfully")
        
        except Exception as e:
            logger.error(f"Error ensuring tables exist: {str(e)}")
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()

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
            name = str(repo_data.get('name', 'unknown'))
            full_name = str(repo_data.get('full_name', 'unknown/unknown'))
            
            # Log the data for debugging
            logger.debug(f"Creating repository: github_id={github_id}, name={name}, full_name={full_name}")
            
            # SQL Server approach to get the last inserted ID
            self.cursor.execute(
                """
                INSERT INTO repositories (github_id, name, full_name) 
                OUTPUT INSERTED.id
                VALUES (?, ?, ?)
                """, 
                (github_id, name, full_name)
            )
            
            # Get the ID directly from the OUTPUT clause
            new_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            return new_id
            
        except Exception as e:
            logger.error(f"Error in get_or_create_repository: {str(e)}")
            logger.error(f"Repository data that caused error: {repo_data}")
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return None
    
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
            username = str(user_data.get('login', 'unknown'))
            avatar_url = str(user_data.get('avatar_url', ''))  # Use empty string as default
            
            # Log the data for debugging
            logger.debug(f"Creating user: github_id={github_id}, username={username}")
            
            # SQL Server approach to get the last inserted ID
            self.cursor.execute(
                """
                INSERT INTO users (github_id, username, avatar_url) 
                OUTPUT INSERTED.id
                VALUES (?, ?, ?)
                """, 
                (github_id, username, avatar_url)
            )
            
            # Get the ID directly from the OUTPUT clause
            new_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            return new_id
            
        except Exception as e:
            logger.error(f"Error in get_or_create_user: {str(e)}")
            logger.error(f"User data that caused error: {user_data}")
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return None
    
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
            
            # Convert timestamps to ISO format for SQLite
            created_at = pr_data.get('created_at', datetime.now().isoformat())
            updated_at = pr_data.get('updated_at', datetime.now().isoformat())
            closed_at = pr_data.get('closed_at')
            merged_at = pr_data.get('merged_at')
            
            # Extract other data with defaults
            title = str(pr_data.get('title', 'Untitled PR'))
            number = int(pr_data.get('number', 0))
            state = str(pr_data.get('state', 'open'))
            html_url = str(pr_data.get('html_url', ''))
            
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
            logger.debug(f"Creating PR: github_id={github_id}, title={title}, repo_id={repository_id}, author_id={author_id}")
            
            self.cursor.execute(
                """INSERT INTO pull_requests 
                   (github_id, repository_id, author_id, title, number, state, html_url, 
                    created_at, updated_at, closed_at, merged_at, last_activity_at) 
                   OUTPUT INSERTED.id
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                (github_id, repository_id, author_id, title, number, state, html_url, 
                 created_at, updated_at, closed_at, merged_at, updated_at)
            )
            
            # Get the ID directly from the OUTPUT clause
            new_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            return new_id
            
        except Exception as e:
            logger.error(f"Error in get_or_create_pull_request: {str(e)}")
            logger.error(f"PR data that caused error: {pr_data}")
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return None
        
        
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
            state = str(review_data.get('state', 'COMMENTED'))
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
            logger.debug(f"Creating review: github_id={github_id}, pr_id={pull_request_id}, reviewer_id={reviewer_id}")
            
            # SQL Server approach to get the last inserted ID
            self.cursor.execute(
                """INSERT INTO pr_reviews 
                   (github_id, pull_request_id, reviewer_id, state, submitted_at) 
                   OUTPUT INSERTED.id
                   VALUES (?, ?, ?, ?, ?)""", 
                (github_id, pull_request_id, reviewer_id, state, submitted_at)
            )
            
            # Get the ID directly from the OUTPUT clause
            review_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            # Update last activity on PR
            self.cursor.execute(
                "UPDATE pull_requests SET last_activity_at = ?, is_stale = 0 WHERE id = ?", 
                (submitted_at, pull_request_id)
            )
            self.conn.commit()
            
            return review_id
            
        except Exception as e:
            logger.error(f"Error in add_pr_review: {str(e)}")
            logger.error(f"Review data that caused error: {review_data}")
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return None    
    
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
            body = str(comment_data.get('body', ''))
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
            logger.debug(f"Creating comment: github_id={github_id}, pr_id={pull_request_id}, author_id={author_id}")
            
            # SQL Server approach to get the last inserted ID
            self.cursor.execute(
                """INSERT INTO review_comments 
                   (github_id, review_id, pull_request_id, author_id, body, created_at, updated_at, contains_command, command_type) 
                   OUTPUT INSERTED.id
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                (github_id, review_id, pull_request_id, author_id, body, created_at, updated_at, contains_command, command_type)
            )
            
            # Get the ID directly from the OUTPUT clause
            comment_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            # Update last activity on PR
            self.cursor.execute(
                "UPDATE pull_requests SET last_activity_at = ?, is_stale = 0 WHERE id = ?", 
                (updated_at, pull_request_id)
            )
            self.conn.commit()
            
            return comment_id
            
        except Exception as e:
            logger.error(f"Error in add_review_comment: {str(e)}")
            logger.error(f"Comment data that caused error: {comment_data}")
            if hasattr(self, 'conn') and self.conn:
                self.conn.rollback()
            return None
    def check_for_stale_prs(self, days_threshold=7):
        """Mark PRs as stale if they haven't had activity in the specified number of days"""
        # Check if we have a valid connection
        if not hasattr(self, 'conn') or not self.conn:
            logger.warning("Database operation skipped due to missing connection")
            return []
            
        try:
            # Calculate the stale date threshold
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
                    "UPDATE pull_requests SET is_stale = 1 WHERE id = ?", 
                    (pr_id,)
                )
                
                # Add to stale PR history
                self.cursor.execute(
                    "INSERT INTO stale_pr_history (pull_request_id) VALUES (?)", 
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
    
    def get_pr_metrics(self):
        """Get metrics for the frontend dashboard"""
        # Check if we have a valid connection
        if not hasattr(self, 'conn') or not self.conn:
            logger.warning("Database operation skipped due to missing connection")
            return {
                'pr_authors': [],
                'active_reviewers': [],
                'command_users': [],
                'stale_pr_count': 0
            }
            
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
            return {
                'pr_authors': [],
                'active_reviewers': [],
                'command_users': [],
                'stale_pr_count': 0
            }