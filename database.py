import os
import psycopg2
import logging
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from models import Base
from dotenv import load_dotenv, find_dotenv
from sqlalchemy.sql import text

# Load environment variables
ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)
else:
    print("Warning: .env file not found")

logger = logging.getLogger('Database')

# Legacy connection function for existing code
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

# SQLAlchemy setup
def get_database_url():
    """Get SQLAlchemy database URL from environment variable"""
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        # Use fallback URL for development
        fallback_url = "postgresql://postgres:postgres@localhost:5432/mypetlink"
        logger.warning(f"DATABASE_URL not found, using default: {fallback_url}")
        db_url = fallback_url
    
    # For SQLAlchemy, prefix with postgresql:// instead of postgres://
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    return db_url

# Create SQLAlchemy engine and session factory with better connection pooling
engine = create_engine(
    get_database_url(), 
    pool_pre_ping=True,  # Test connections before using them
    pool_recycle=3600,   # Recycle connections after an hour
    pool_timeout=30      # Wait up to 30 seconds for a connection
)
session_factory = sessionmaker(bind=engine)
SessionLocal = scoped_session(session_factory)

# Initialize database (create tables)
def init_db():
    Base.metadata.create_all(bind=engine)

# Session management
def get_db_session():
    """Get a new database session with improved error handling"""
    try:
        db = SessionLocal()
        # Test the connection
        db.execute(text("SELECT 1"))
        return db
    except Exception as e:
        logger.error(f"Database session creation error: {e}")
        # Attempt to close if session was created
        try:
            if 'db' in locals():
                db.close()
        except:
            pass
        # Return a new session as a fallback (may fail again but worth trying)
        try:
            return SessionLocal()
        except Exception as retry_error:
            logger.error(f"Failed to create database session on retry: {retry_error}")
            raise

def close_db_session(db):
    """Close database session safely"""
    if db is not None:
        try:
            db.close()
        except Exception as e:
            logger.error(f"Error closing database session: {e}")
            # No need to re-raise, just log the error

# Initialize database on module import
try:
    init_db()
except Exception as e:
    logger.warning(f"Database initialization skipped: {e}")
    logger.warning("Tables will need to be created manually or the application may not function properly")
