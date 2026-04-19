#!/bin/bash
# Database Setup Script for Evidence Analysis System - Phase 1

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Evidence Analysis System - Database Setup${NC}"
echo "=========================================="

# Load environment variables if .env exists
if [ -f .env ]; then
    echo -e "${YELLOW}Loading environment variables from .env${NC}"
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}ERROR: DATABASE_URL environment variable is not set${NC}"
    echo "Please set DATABASE_URL in .env file or environment"
    echo "Example: postgresql://user:password@localhost:5432/evidence_analysis"
    exit 1
fi

echo -e "${GREEN}Database URL: ${NC}$DATABASE_URL"

# Extract database name from DATABASE_URL
DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')

echo -e "\n${YELLOW}Step 1: Creating database (if not exists)${NC}"
# Try to create database (ignore error if it already exists)
psql $DATABASE_URL -c "SELECT 1;" 2>/dev/null || {
    echo "Database does not exist, attempting to create..."
    # Connect to postgres database to create new database
    BASE_URL=$(echo $DATABASE_URL | sed "s/\/$DB_NAME/\/postgres/")
    psql $BASE_URL -c "CREATE DATABASE $DB_NAME;" || echo "Database may already exist"
}

echo -e "\n${YELLOW}Step 2: Running schema creation${NC}"
psql $DATABASE_URL -f db/schema.sql

echo -e "\n${GREEN}✓ Database setup completed successfully!${NC}"
echo -e "\nDatabase: ${GREEN}$DB_NAME${NC}"
echo -e "Tables created:"
echo "  - users"
echo "  - executions"

echo -e "\n${YELLOW}To verify tables:${NC}"
echo "  psql $DATABASE_URL -c '\dt'"

echo -e "\n${YELLOW}To drop all tables (CAUTION: Data will be lost):${NC}"
echo "  psql $DATABASE_URL -f db/drop_schema.sql"
