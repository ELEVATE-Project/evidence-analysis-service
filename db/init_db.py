#!/usr/bin/env python3
"""
Database initialization script using SQLAlchemy
This script creates all tables defined in models
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import engine, Base
from models.user import User
from models.execution import Execution
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db():
    """Initialize database by creating all tables"""
    logger.info("Creating database tables...")
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("✓ Database tables created successfully!")
        
        # List created tables
        logger.info("\nCreated tables:")
        for table in Base.metadata.sorted_tables:
            logger.info(f"  - {table.name}")
            
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        sys.exit(1)


def drop_db():
    """Drop all database tables"""
    logger.warning("⚠ Dropping all database tables...")
    response = input("Are you sure? This will delete all data. Type 'yes' to confirm: ")
    
    if response.lower() != 'yes':
        logger.info("Operation cancelled")
        return
    
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("✓ All tables dropped successfully!")
    except Exception as e:
        logger.error(f"Error dropping tables: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database initialization script")
    parser.add_argument(
        '--drop',
        action='store_true',
        help='Drop all tables (WARNING: deletes all data)'
    )
    
    args = parser.parse_args()
    
    if args.drop:
        drop_db()
    else:
        init_db()
