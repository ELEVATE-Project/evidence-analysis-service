#!/usr/bin/env python3
"""
Pre-start bootstrap script — validates cloud storage and uploads sample CSVs.

This script is invoked by the Docker backend command before uvicorn starts:

    alembic upgrade head
    python scripts/upload_sample_csvs.py   ← this file
    uvicorn main:app ...

It delegates entirely to services.bootstrap.run_bootstrap, which is the same
code path used by main.py's lifespan. Running it in Docker before uvicorn
ensures sample CSVs are in the bucket before the first request arrives.

For native (non-Docker) setups, main.py's lifespan handles this automatically,
so running this script manually is not required.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Allow imports from the project root when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.database import SessionLocal
from db.seed_data import seed_default_csv_source_types, seed_default_users
from services.bootstrap import run_bootstrap

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _run() -> None:
    db = SessionLocal()
    try:
        logger.info("Applying seed data...")
        seed_default_users(db)
        seed_default_csv_source_types(db)
        logger.info("Seed data applied")

        await run_bootstrap(db)
    finally:
        db.close()


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except Exception:
        logger.exception("Bootstrap script failed — aborting startup")
        sys.exit(1)
