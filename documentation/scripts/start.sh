#!/bin/bash

# Evidence Analysis System - Start All Services Script
# This script starts all required services for local development

set -e

echo "=========================================="
echo "Starting Evidence Analysis System"
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
    echo -e "${YELLOW}!${NC} $1"
}

# Detect OS
OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/../.."

# Step 1: Start PostgreSQL
echo "Step 1: Starting PostgreSQL..."

if [ "$OS" == "macos" ]; then
    brew services start postgresql@16 2>/dev/null || brew services start postgresql
    print_status "PostgreSQL started"
elif [ "$OS" == "linux" ]; then
    sudo systemctl start postgresql
    print_status "PostgreSQL started"
fi

sleep 2

# Verify PostgreSQL
pg_isready -h localhost -U postgres > /dev/null 2>&1 && print_status "PostgreSQL is ready" || print_error "PostgreSQL failed to start"

echo ""

# Step 2: Start RabbitMQ
echo "Step 2: Starting RabbitMQ..."

if [ "$OS" == "macos" ]; then
    brew services start rabbitmq
    print_status "RabbitMQ started"
elif [ "$OS" == "linux" ]; then
    sudo systemctl start rabbitmq-server
    print_status "RabbitMQ started"
fi

sleep 3

# Verify RabbitMQ
curl -s http://localhost:15672/api/overview -u guest:guest > /dev/null 2>&1 && print_status "RabbitMQ is ready" || print_warning "RabbitMQ may need more time to start"

echo ""

# Step 3: Start Redis (optional)
echo "Step 3: Starting Redis (optional)..."

if command -v redis-server >/dev/null 2>&1; then
    if [ "$OS" == "macos" ]; then
        brew services start redis 2>/dev/null
    elif [ "$OS" == "linux" ]; then
        sudo systemctl start redis-server 2>/dev/null
    fi
    print_status "Redis started"
else
    print_warning "Redis not found (optional)"
fi

echo ""

# Step 4: Start Backend API
echo "Step 4: Starting Backend API..."

cd "$BACKEND_DIR"

if [ ! -d "venv" ]; then
    print_error "Virtual environment not found. Run setup.sh first."
    exit 1
fi

# Check if backend is already running
if lsof -i :8000 > /dev/null 2>&1; then
    print_warning "Backend already running on port 8000"
else
    # Start in background
    source venv/bin/activate
    nohup uvicorn main:app --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > /tmp/evidence-backend.pid
    print_status "Backend started (PID: $BACKEND_PID)"
fi

sleep 3

# Verify backend
curl -s http://localhost:8000/health > /dev/null 2>&1 && print_status "Backend is ready" || print_warning "Backend may need more time to start"

echo ""

# Step 5: Start Celery Worker
echo "Step 5: Starting Celery Worker..."

if pgrep -f "celery worker" > /dev/null; then
    print_warning "Celery worker already running"
else
    source venv/bin/activate
    nohup celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2 > logs/celery.log 2>&1 &
    CELERY_PID=$!
    echo $CELERY_PID > /tmp/evidence-celery.pid
    print_status "Celery worker started (PID: $CELERY_PID)"
fi

echo ""

# Step 6: Start Frontend (if exists)
echo "Step 6: Starting Frontend..."

FRONTEND_DIR="$BACKEND_DIR/../evidence-analysis-portal-p1"

if [ -d "$FRONTEND_DIR" ]; then
    cd "$FRONTEND_DIR"
    
    if lsof -i :5173 > /dev/null 2>&1; then
        print_warning "Frontend already running on port 5173"
    else
        nohup npm run dev > logs/frontend.log 2>&1 &
        FRONTEND_PID=$!
        echo $FRONTEND_PID > /tmp/evidence-frontend.pid
        print_status "Frontend started (PID: $FRONTEND_PID)"
    fi
else
    print_warning "Frontend directory not found"
fi

echo ""

# Summary
echo "=========================================="
echo "All Services Started!"
echo "=========================================="
echo ""
echo "Services:"
echo "  ✓ PostgreSQL:     localhost:5432"
echo "  ✓ RabbitMQ:       localhost:5672"
echo "  ✓ RabbitMQ UI:    http://localhost:15672 (guest/guest)"
echo "  ✓ Backend API:    http://localhost:8000"
echo "  ✓ API Docs:       http://localhost:8000/docs"
echo "  ✓ Celery Worker:  Running"
if [ -d "$FRONTEND_DIR" ]; then
echo "  ✓ Frontend:       http://localhost:5173"
fi
echo ""
echo "Logs:"
echo "  Backend:  $BACKEND_DIR/logs/backend.log"
echo "  Celery:   $BACKEND_DIR/logs/celery.log"
if [ -d "$FRONTEND_DIR" ]; then
echo "  Frontend: $FRONTEND_DIR/logs/frontend.log"
fi
echo ""
echo "To stop all services, run: ./stop.sh"
echo ""
