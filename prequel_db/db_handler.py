import logging
from prequel_db.db_models import DatabaseModels
from prequel_db.db_analytics import DatabaseAnalytics

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DatabaseHandler(DatabaseModels, DatabaseAnalytics):
    """
    Main database handler that combines models and analytics functionality
    
    This class serves as the primary interface for database operations,
    inheriting both model operations (CRUD for repositories, users, PRs)
    and analytics functions (stale PR tracking, metrics reporting).
    """
    
    def __init__(self):
        """
        Initialize database connection by calling parent class initializer
        """
        super().__init__()
        logger.info("DatabaseHandler initialized")
    
    def check_connection(self):
        """
        Check if the database connection is active and working
        """
        if not hasattr(self, 'conn') or not self.conn:
            logger.error("No active database connection")
            return False
            
        try:
            # Try a simple query to check connection
            self.cursor.execute("SELECT 1")
            result = self.cursor.fetchone()
            return result is not None
        except Exception as e:
            logger.error(f"Error checking database connection: {str(e)}")
            return False