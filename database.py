import os
import psycopg2
import logging
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

logger = logging.getLogger('Database')

def get_db_connection():
    try:
        # Parse DATABASE_URL
        db_url = os.getenv('DATABASE_URL')
        url = urlparse(db_url)
        
        conn = psycopg2.connect(
            dbname=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port,
            sslmode='require'  # Add SSL mode
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return None 
