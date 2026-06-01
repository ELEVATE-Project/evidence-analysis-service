"""
Dev-only helper: create the database named in DATABASE_URL if it does not
exist.

WHEN TO USE THIS SCRIPT
-----------------------
  Local development and CI environments where PostgreSQL is running but the
  target database has never been created.

  Run once after cloning the repo:
      source venv/bin/activate
      python scripts/create_dev_db.py
      alembic upgrade head

  It is safe to re-run — it skips creation if the database already exists.

NOT FOR PRODUCTION
------------------
  In production the database is pre-created by infrastructure-as-code
  (Terraform / CloudFormation / Cloud SQL provisioning).  The application user
  does NOT hold CREATEDB privileges in production.  Migrations are run by a
  dedicated pre-deploy job in the CI/CD pipeline.  See documentation/setup-docker.md
  for the production-grade pattern used in Docker/K8s deployments.
"""
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: load .env from the project root so DATABASE_URL is available
# even when this script is run from any working directory.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    # python-dotenv is in requirements.txt; this branch should never be hit
    # inside an activated virtualenv, but guard for safety.
    pass

try:
    import psycopg2
    from psycopg2 import sql as pgsql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("ERROR: psycopg2 is not installed.  Activate the virtualenv first:")
    print("  source venv/bin/activate")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_db_url(url: str) -> dict:
    """Return connection parameters parsed from a postgresql:// URL."""
    m = re.match(
        r"postgresql(?:\+\w+)?://"
        r"(?P<user>[^:@]+)"
        r"(?::(?P<password>[^@]*))?"
        r"@(?P<host>[^:/]+)"
        r"(?::(?P<port>\d+))?"
        r"/(?P<dbname>[^?]+)",
        url,
    )
    if not m:
        raise ValueError(
            f"Cannot parse DATABASE_URL: {url!r}\n"
            f"Expected format: postgresql://user:password@host:port/dbname"
        )
    return {
        "user": m.group("user"),
        "password": m.group("password") or "",
        "host": m.group("host"),
        "port": int(m.group("port") or 5432),
        "dbname": m.group("dbname"),
    }


def _db_exists(params: dict) -> bool:
    """Return True if the target database already exists."""
    conn = psycopg2.connect(
        host=params["host"],
        port=params["port"],
        user=params["user"],
        password=params["password"],
        dbname="postgres",   # maintenance DB — always present
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (params["dbname"],),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def _create_db(params: dict) -> None:
    """Create the target database (autocommit required for CREATE DATABASE)."""
    conn = psycopg2.connect(
        host=params["host"],
        port=params["port"],
        user=params["user"],
        password=params["password"],
        dbname="postgres",
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute(
                pgsql.SQL("CREATE DATABASE {}").format(
                    pgsql.Identifier(params["dbname"])
                )
            )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  Evidence Analysis — Create Dev Database")
    print("=" * 60)

    # ---- 1. Load DATABASE_URL -------------------------------------------
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print(
            "\nERROR: DATABASE_URL is not set.\n"
            "\n"
            "  Run:  cp .env.example .env\n"
            "  Then fill in DATABASE_URL and re-run this script.\n"
        )
        sys.exit(1)

    try:
        params = _parse_db_url(db_url)
    except ValueError as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)

    print(f"\n  Host      : {params['host']}:{params['port']}")
    print(f"  User      : {params['user']}")
    print(f"  Database  : {params['dbname']}")

    # ---- 2. Verify server reachability ------------------------------------
    print("\n[1/2] Checking PostgreSQL connectivity...")
    try:
        reachable = _db_exists(params)   # side-effect: also checks auth
    except psycopg2.OperationalError as exc:
        msg = str(exc).strip()
        print(f"\n  ERROR: Cannot connect to PostgreSQL.\n  {msg}")
        print(
            "\n  Checklist:\n"
            "    • Is PostgreSQL running?  (pg_isready -h localhost)\n"
            "    • Are the user/password in DATABASE_URL correct?\n"
            "    • Is the host/port reachable?\n"
        )
        sys.exit(1)
    print("  PostgreSQL is reachable.")

    # ---- 3. Create database if missing ------------------------------------
    print(f"\n[2/2] Ensuring database '{params['dbname']}' exists...")
    if reachable:
        print(f"  Already exists — skipping CREATE DATABASE.")
    else:
        try:
            _create_db(params)
            print(f"  Created database '{params['dbname']}'.")
        except psycopg2.Error as exc:
            print(f"\n  ERROR: Could not create database.\n  {exc}")
            print(
                "\n  If the user lacks CREATEDB privilege, create the database\n"
                "  manually as a superuser and re-run this script:\n"
                f"\n    createdb -U postgres -h {params['host']} {params['dbname']}\n"
            )
            sys.exit(1)

    print(
        f"\n{'=' * 60}\n"
        f"  Database ready.\n"
        f"\n"
        f"  Next: apply migrations\n"
        f"    alembic upgrade head\n"
        f"{'=' * 60}\n"
    )


if __name__ == "__main__":
    main()
