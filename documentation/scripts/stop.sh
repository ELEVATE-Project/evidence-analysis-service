#!/bin/bash

# Evidence Analysis System - Stop All Services Script
# This script stops all running services

set -e

echo "=========================================="
echo "Stopping Evidence Analysis System"
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

# Detect OS
OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
fi

# Step 1: Stop Frontend
echo "Step 1: Stopping Frontend..."

if [ -f "/tmp/evidence-frontend.pid" ]; then
    kill $(cat /tmp/evidence-frontend.pid) 2>/dev/null || true
    rm /tmp/evidence-frontend.pid
    print_status "Frontend stopped"
else
    # Try to find and kill
    PID=$(lsof -t -i:5173 2>/dev/null)
    if [ -n "$PID" ]; then
        kill $PID
        print_status "Frontend stopped"
    else
        print_status "Frontend not running"
    fi
fi

echo ""

# Step 2: Stop Celery Worker
echo "Step 2: Stopping Celery Worker..."

if [ -f "/tmp/evidence-celery.pid" ]; then
    kill $(cat /tmp/evidence-celery.pid) 2>/dev/null || true
    rm /tmp/evidence-celery.pid
    print_status "Celery worker stopped"
else
    # Try to find and kill
    pkill -f "celery worker" 2>/dev/null && print_status "Celery worker stopped" || print_status "Celery worker not running"
fi

echo ""

# Step 3: Stop Backend API
echo "Step 3: Stopping Backend API..."

if [ -f "/tmp/evidence-backend.pid" ]; then
    kill $(cat /tmp/evidence-backend.pid) 2>/dev/null || true
    rm /tmp/evidence-backend.pid
    print_status "Backend stopped"
else
    # Try to find and kill
    PID=$(lsof -t -i:8000 2>/dev/null)
    if [ -n "$PID" ]; then
        kill $PID
        print_status "Backend stopped"
    else
        print_status "Backend not running"
    fi
fi

echo ""

# Step 4: Stop Redis (optional)
echo "Step 4: Stopping Redis..."

if [ "$OS" == "macos" ]; then
    brew services stop redis 2>/dev/null && print_status "Redis stopped" || print_status "Redis not running"
elif [ "$OS" == "linux" ]; then
    sudo systemctl stop redis-server 2>/dev/null && print_status "Redis stopped" || print_status "Redis not running"
fi

echo ""

# Step 5: Stop RabbitMQ
echo "Step 5: Stopping RabbitMQ..."

if [ "$OS" == "macos" ]; then
    brew services stop rabbitmq
    print_status "RabbitMQ stopped"
elif [ "$OS" == "linux" ]; then
    sudo systemctl stop rabbitmq-server
    print_status "RabbitMQ stopped"
fi

echo ""

# Step 6: Stop PostgreSQL
echo "Step 6: Stopping PostgreSQL..."

if [ "$OS" == "macos" ]; then
    brew services stop postgresql@16 2>/dev/null || brew services stop postgresql
    print_status "PostgreSQL stopped"
elif [ "$OS" == "linux" ]; then
    sudo systemctl stop postgresql
    print_status "PostgreSQL stopped"
fi

echo ""

# Summary
echo "=========================================="
echo "All Services Stopped!"
echo "=========================================="
echo ""
echo "To start services again, run: ./start.sh"
echo ""
