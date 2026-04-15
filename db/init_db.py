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
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
import psycopg2
from psycopg2 import sql

from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ensure_database_exists() -> bool:
    """
    Ensure target database exists.
    Returns True if database was created, False if it already existed.
    """
    db_url = make_url(settings.DATABASE_URL)
    db_name = db_url.database

    if not db_name:
        raise ValueError("DATABASE_URL does not include a database name")

    admin_url = db_url.set(database="postgres")
    admin_dsn = admin_url.render_as_string(hide_password=False).replace(
        "postgresql+psycopg2://",
        "postgresql://",
    )

    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if cur.fetchone():
                return False

            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            return True
    finally:
        conn.close()


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
    
    except OperationalError as e:
        if "does not exist" not in str(e).lower():
            logger.error(f"Error creating tables: {str(e)}")
            sys.exit(1)

        logger.warning("Database does not exist. Attempting to create it...")

        try:
            created = ensure_database_exists()
            if created:
                logger.info("✓ Database created successfully. Retrying table creation...")
            else:
                logger.info("Database already exists. Retrying table creation...")

            engine.dispose()
            Base.metadata.create_all(bind=engine)
            logger.info("✓ Database tables created successfully!")

            logger.info("\nCreated tables:")
            for table in Base.metadata.sorted_tables:
                logger.info(f"  - {table.name}")
        except Exception as create_err:
            logger.error(f"Error creating database or tables: {str(create_err)}")
            sys.exit(1)

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
