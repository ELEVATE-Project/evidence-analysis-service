#!/bin/bash

# Evidence Analysis System - Health Check Script
# This script verifies all services are running correctly

echo "=========================================="
echo "Evidence Analysis System - Health Check"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() {
    echo -e "  ${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "  ${RED}✗${NC} $1"
}

print_warning() {
    echo -e "  ${YELLOW}!${NC} $1"
}

CHECKS_PASSED=0
CHECKS_FAILED=0

# Check PostgreSQL
echo "1. PostgreSQL:"
if pg_isready -h localhost -U postgres > /dev/null 2>&1; then
    print_success "PostgreSQL is running"
    ((CHECKS_PASSED++))
else
    print_error "PostgreSQL is not running"
    ((CHECKS_FAILED++))
fi

# Check database exists
if psql -U postgres -h localhost -d evidence_analysis -c "\dt" > /dev/null 2>&1; then
    print_success "Database 'evidence_analysis' exists"
    ((CHECKS_PASSED++))
else
    print_error "Database 'evidence_analysis' not found"
    ((CHECKS_FAILED++))
fi

echo ""

# Check RabbitMQ
echo "2. RabbitMQ:"
if curl -s http://localhost:15672/api/overview -u guest:guest > /dev/null 2>&1; then
    print_success "RabbitMQ is running"
    ((CHECKS_PASSED++))
    
    # Check queue exists
    if curl -s http://localhost:15672/api/queues/%2F/execution_queue -u guest:guest | grep -q "execution_queue"; then
        print_success "Execution queue exists"
        ((CHECKS_PASSED++))
    else
        print_warning "Execution queue not found"
    fi
else
    print_error "RabbitMQ is not running"
    ((CHECKS_FAILED++))
fi

echo ""

# Check Redis (optional)
echo "3. Redis (optional):"
if redis-cli ping > /dev/null 2>&1; then
    print_success "Redis is running"
    ((CHECKS_PASSED++))
else
    print_warning "Redis is not running (optional)"
fi

echo ""

# Check Backend API
echo "4. Backend API:"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    print_success "Backend is running"
    ((CHECKS_PASSED++))
    
    # Check API response
    HEALTH=$(curl -s http://localhost:8000/health)
    if echo "$HEALTH" | grep -q "healthy"; then
        print_success "Backend is healthy"
        ((CHECKS_PASSED++))
    else
        print_error "Backend health check failed"
        ((CHECKS_FAILED++))
    fi
else
    print_error "Backend is not running"
    ((CHECKS_FAILED++))
fi

echo ""

# Check Celery Worker
echo "5. Celery Worker:"
if pgrep -f "celery worker" > /dev/null 2>&1; then
    print_success "Celery worker is running"
    ((CHECKS_PASSED++))
    
    # Check worker status
    cd "$(dirname "$0")/../.."
    if [ -d "venv" ]; then
        source venv/bin/activate
        if celery -A celery_worker.celery_app inspect ping > /dev/null 2>&1; then
            print_success "Celery worker is responsive"
            ((CHECKS_PASSED++))
        else
            print_warning "Celery worker not responding"
        fi
    fi
else
    print_error "Celery worker is not running"
    ((CHECKS_FAILED++))
fi

echo ""

# Check Frontend (optional)
echo "6. Frontend (optional):"
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    print_success "Frontend is running"
    ((CHECKS_PASSED++))
else
    print_warning "Frontend is not running"
fi

echo ""

# Summary
echo "=========================================="
echo "Health Check Summary"
echo "=========================================="
echo ""
echo "  Passed: $CHECKS_PASSED"
echo "  Failed: $CHECKS_FAILED"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical services are running!${NC}"
    echo ""
    echo "Endpoints:"
    echo "  • Backend API:    http://localhost:8000"
    echo "  • API Docs:       http://localhost:8000/docs"
    echo "  • Frontend:       http://localhost:5173"
    echo "  • RabbitMQ UI:    http://localhost:15672"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some services are not running properly${NC}"
    echo ""
    echo "Run './start.sh' to start all services"
    echo ""
    exit 1
fi
