#!/bin/bash

# Evidence Analysis System - Automated Setup Script
# This script automates the installation and configuration process

set -e  # Exit on error

echo "=========================================="
echo "Evidence Analysis System - Setup Script"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect OS
OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
fi

echo -e "${GREEN}Detected OS: $OS${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Check prerequisites
echo "Step 1: Checking prerequisites..."

if command_exists python3.12; then
    print_status "Python 3.12 found: $(python3.12 --version)"
else
    print_error "Python 3.12 not found"
    echo "Please install Python 3.12 first:"
    if [ "$OS" == "macos" ]; then
        echo "  brew install python@3.12"
    elif [ "$OS" == "linux" ]; then
        echo "  sudo add-apt-repository ppa:deadsnakes/ppa"
        echo "  sudo apt update && sudo apt install python3.12"
    fi
    exit 1
fi

if command_exists psql; then
    print_status "PostgreSQL found: $(psql --version)"
else
    print_error "PostgreSQL not found"
    exit 1
fi

if command_exists node; then
    print_status "Node.js found: $(node --version)"
else
    print_warning "Node.js not found (required for frontend)"
fi

if command_exists rabbitmq-server; then
    print_status "RabbitMQ found"
else
    print_warning "RabbitMQ not found (required for background processing)"
fi

echo ""

# Step 2: Create virtual environment
echo "Step 2: Creating Python virtual environment..."

if [ -d "venv" ]; then
    print_warning "Virtual environment already exists, skipping..."
else
    python3.12 -m venv venv
    print_status "Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate
print_status "Virtual environment activated"

echo ""

# Step 3: Install Python dependencies
echo "Step 3: Installing Python dependencies..."

pip install --upgrade pip > /dev/null 2>&1
pip install wheel > /dev/null 2>&1
pip install -r requirements.txt
print_status "Python dependencies installed"

echo ""

# Step 4: Configure environment
echo "Step 4: Configuring environment..."

if [ -f ".env" ]; then
    print_warning ".env file already exists, skipping..."
else
    cp .env.example .env
    print_status ".env file created"
    
    # Generate JWT secret
    JWT_SECRET=$(openssl rand -hex 32)
    if [ "$OS" == "macos" ]; then
        sed -i '' "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$JWT_SECRET/" .env
    else
        sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$JWT_SECRET/" .env
    fi
    print_status "JWT secret generated"
    
    print_warning "Please update the following in .env:"
    echo "  - DATABASE_URL"
    echo "  - GEMINI_API_KEY_1"
    echo "  - Cloud storage credentials"
    echo "  - SMTP credentials"
fi

echo ""

# Step 5: Database setup
echo "Step 5: Setting up database..."

read -p "Create database 'evidence_analysis'? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    createdb -U postgres evidence_analysis 2>/dev/null || print_warning "Database may already exist"
    print_status "Database created"
    
    # Initialize schema
    python db/init_db.py
    print_status "Database schema initialized"
    
    # Seed users
    python db/seed_data.py
    print_status "Default users seeded"
    
    # Run migrations
    alembic upgrade head
    print_status "Migrations applied"
fi

echo ""

# Step 6: Frontend setup (if exists)
if [ -d "../evidence-analysis-portal-p1" ]; then
    echo "Step 6: Setting up frontend..."
    
    cd ../evidence-analysis-portal-p1
    
    if command_exists npm; then
        if [ ! -f ".env" ]; then
            cp .env.example .env
            print_status "Frontend .env created"
        fi
        
        npm install
        print_status "Frontend dependencies installed"
    else
        print_warning "npm not found, skipping frontend setup"
    fi
    
    cd ../evidence-analysis-service-p1
fi

echo ""

# Step 7: Verify setup
echo "Step 7: Verifying setup..."

# Check database connection
python -c "from db.database import engine; engine.connect()" 2>/dev/null && print_status "Database connection OK" || print_error "Database connection failed"

# Check virtual environment
python -c "import fastapi; import celery; import sqlalchemy" 2>/dev/null && print_status "Python dependencies OK" || print_error "Python dependencies check failed"

echo ""

# Summary
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Update .env with your credentials"
echo "2. Start PostgreSQL: brew services start postgresql@16 (macOS) or sudo systemctl start postgresql (Linux)"
echo "3. Start RabbitMQ: brew services start rabbitmq (macOS) or sudo systemctl start rabbitmq-server (Linux)"
echo "4. Start backend: source venv/bin/activate && uvicorn main:app --reload"
echo "5. Start Celery worker: celery -A celery_worker.celery_app worker --loglevel=info"
echo "6. Start frontend: cd ../evidence-analysis-portal-p1 && npm run dev"
echo ""
echo "Default login credentials:"
echo "  Username: admin"
echo "  Password: admin123"
echo ""
echo "API Documentation: http://localhost:8000/docs"
echo "Frontend: http://localhost:5173"
echo ""
