#!/bin/bash

# Evidence Analysis System - Reset Database Script
# ⚠️  WARNING: This will DELETE ALL DATA in the database!

set -e

echo "=========================================="
echo "Database Reset Script"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/../.."

cd "$BACKEND_DIR"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Warning
echo -e "${RED}WARNING: This will DELETE ALL DATA in the database!${NC}"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " -r
echo

if [ "$REPLY" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""

# Step 1: Backup existing data (optional)
echo "Step 1: Creating backup (optional)..."

read -p "Create a backup before reset? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="backup_${TIMESTAMP}.sql"
    
    pg_dump -U postgres -h localhost -d evidence_analysis > "$BACKUP_FILE" 2>/dev/null && print_status "Backup created: $BACKUP_FILE" || print_warning "Backup failed (database may not exist)"
fi

echo ""

# Step 2: Drop and recreate database
echo "Step 2: Dropping and recreating database..."

# Drop database
dropdb -U postgres -h localhost evidence_analysis 2>/dev/null || print_warning "Database may not exist"
print_status "Database dropped"

# Create database
createdb -U postgres -h localhost evidence_analysis
print_status "Database created"

echo ""

# Step 3: Initialize schema
echo "Step 3: Initializing schema..."

python db/init_db.py
print_status "Schema initialized"

echo ""

# Step 4: Seed default users
echo "Step 4: Seeding default users..."

python db/seed_data.py
print_status "Default users seeded"

echo ""

# Step 5: Run migrations
echo "Step 5: Running migrations..."

alembic upgrade head
print_status "Migrations applied"

echo ""

# Step 6: Verify database
echo "Step 6: Verifying database..."

# Check tables
TABLE_COUNT=$(psql -U postgres -h localhost -d evidence_analysis -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")

if [ "$TABLE_COUNT" -gt 0 ]; then
    print_status "Database has $TABLE_COUNT tables"
else
    print_error "Database verification failed"
    exit 1
fi

# Check users
USER_COUNT=$(psql -U postgres -h localhost -d evidence_analysis -t -c "SELECT COUNT(*) FROM users;")
print_status "Database has $USER_COUNT users"

echo ""

# Summary
echo "=========================================="
echo "Database Reset Complete!"
echo "=========================================="
echo ""
echo "Default login credentials:"
echo "  👤 Username: admin"
echo "  🔑 Password: admin123"
echo ""
echo "  👤 Username: program_designer"
echo "  🔑 Password: user123"
echo ""
echo "  👤 Username: analyst"
echo "  🔑 Password: user123"
echo ""
echo "⚠️  Remember to change default passwords in production!"
echo ""
