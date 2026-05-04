# Troubleshooting Guide - Evidence Analysis System

Comprehensive guide for resolving common issues in the Evidence Analysis System.

---

## Table of Contents

- [Installation Issues](#installation-issues)
- [Database Issues](#database-issues)
- [Backend API Issues](#backend-api-issues)
- [Frontend Issues](#frontend-issues)
- [RabbitMQ & Celery Issues](#rabbitmq--celery-issues)
- [Cloud Storage Issues](#cloud-storage-issues)
- [Email Notification Issues](#email-notification-issues)
- [Performance Issues](#performance-issues)
- [Docker Issues](#docker-issues)
- [Common Error Messages](#common-error-messages)

---

## Installation Issues

### Python Version Mismatch

**Problem**: `python: command not found` or wrong Python version

```bash
# Check Python version
python --version
python3 --version
python3.12 --version

# macOS: Install specific version
brew install python@3.12

# Ubuntu: Install from deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12

# Create symlink
sudo ln -s /usr/bin/python3.12 /usr/local/bin/python
```

### pip Install Fails

**Problem**: `pip install -r requirements.txt` fails with compilation errors

```bash
# Install development headers (Ubuntu)
sudo apt install -y python3.12-dev libpq-dev build-essential

# Install development headers (macOS)
brew install postgresql

# Upgrade pip
pip install --upgrade pip wheel setuptools

# Try installing dependencies one by one
cat requirements.txt | xargs -n 1 pip install
```

### Virtual Environment Issues

**Problem**: Cannot activate virtual environment

```bash
# Recreate virtual environment
rm -rf venv
python3.12 -m venv venv

# On macOS/Linux
source venv/bin/activate

# On Windows
venv\Scripts\activate

# Verify activation
which python  # Should point to venv/bin/python
```

### Node.js / npm Issues

**Problem**: `npm install` fails or slow

```bash
# Clear npm cache
npm cache clean --force

# Remove node_modules and package-lock
rm -rf node_modules package-lock.json

# Reinstall
npm install

# Use different registry if slow
npm config set registry https://registry.npmmirror.com

# Reset to default
npm config set registry https://registry.npmjs.org
```

---

## Database Issues

### Cannot Connect to PostgreSQL

**Problem**: `psql: could not connect to server`

```bash
# Check if PostgreSQL is running
# macOS
brew services list | grep postgresql

# Ubuntu
sudo systemctl status postgresql

# Start PostgreSQL
# macOS
brew services start postgresql@16

# Ubuntu
sudo systemctl start postgresql

# Check port
sudo lsof -i :5432
sudo netstat -tuln | grep 5432

# Test connection
psql -h localhost -U postgres -d postgres
```

### Authentication Failed

**Problem**: `FATAL: password authentication failed for user "postgres"`

```bash
# Reset PostgreSQL password
sudo -u postgres psql

# In psql:
ALTER USER postgres PASSWORD 'postgres';
\q

# Update pg_hba.conf (Ubuntu)
sudo nano /etc/postgresql/16/main/pg_hba.conf

# Change from 'peer' to 'md5':
local   all             postgres                                md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Database Does Not Exist

**Problem**: `database "evidence_analysis" does not exist`

```bash
# Create database
createdb -U postgres evidence_analysis

# Or in psql:
sudo -u postgres psql
CREATE DATABASE evidence_analysis;
\q
```

### Migration Errors

**Problem**: Alembic migration fails

```bash
# Check current migration status
alembic current

# View migration history
alembic history --verbose

# Stamp database to specific revision (⚠️ careful!)
alembic stamp head

# Rollback one migration
alembic downgrade -1

# Drop all tables and reinitialize
python db/init_db.py
alembic upgrade head
```

### Database Connection Pool Exhausted

**Problem**: `OperationalError: connection pool exhausted`

```python
# In db/database.py, increase pool size:
engine = create_engine(
    DATABASE_URL,
    pool_size=20,  # Increase from default 5
    max_overflow=40,
    pool_pre_ping=True
)
```

---

## Backend API Issues

### Port Already in Use

**Problem**: `Address already in use` on port 8000

```bash
# Find process using port 8000
# macOS/Linux
lsof -i :8000

# Kill process
kill -9 <PID>

# Or use different port
uvicorn main:app --port 8001
```

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'fastapi'`

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Verify installation
pip list | grep fastapi

# Reinstall dependencies
pip install --upgrade --force-reinstall -r requirements.txt

# Check Python path
python -c "import sys; print(sys.path)"
```

### JWT Authentication Fails

**Problem**: `Invalid token` or `Could not validate credentials`

```bash
# Generate new JWT secret
openssl rand -hex 32

# Update .env
JWT_SECRET_KEY=<new-secret>

# Restart backend
# Users will need to log in again
```

### CORS Errors

**Problem**: `No 'Access-Control-Allow-Origin' header present`

```env
# Update CORS_ORIGINS in .env
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# Include all frontend URLs
# For production:
CORS_ORIGINS=["https://yourdomain.com"]
```

### Slow API Response

**Problem**: API endpoints taking too long

```bash
# Enable query logging
# In database.py
engine = create_engine(DATABASE_URL, echo=True)

# Check database connections
docker-compose exec postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Profile endpoint
import cProfile
cProfile.run('your_function()')

# Check for N+1 queries (use SQLAlchemy relationships with joinedload)
```

### File Upload Fails

**Problem**: `413 Request Entity Too Large`

```env
# Increase MAX_UPLOAD_SIZE in .env
MAX_UPLOAD_SIZE=209715200  # 200 MB

# If using Nginx, update nginx.conf:
client_max_body_size 200M;
```

---

## Frontend Issues

### Blank Page on Load

**Problem**: Frontend shows blank page

```bash
# Check browser console for errors (F12)
# Common causes:

# 1. API endpoint unreachable
# Verify backend is running
curl http://localhost:8000/health

# 2. Environment variables missing
cat .env

# 3. Build errors
npm run build
# Check for errors in output

# 4. Clear browser cache
# Ctrl+Shift+R (hard reload)
```

### API Requests Failing

**Problem**: `Network Error` or `404 Not Found`

```bash
# Check API endpoint in .env
API_ENDPOINT=http://localhost:8000

# Verify backend is running
curl http://localhost:8000/health

# Check CORS configuration in backend .env
CORS_ORIGINS=["http://localhost:5173"]

# Check browser console for CORS errors
```

### Login Not Working

**Problem**: Cannot log in with default credentials

```bash
# Verify users exist in database
docker-compose exec postgres psql -U postgres -d evidence_analysis -c "SELECT username FROM users;"

# Reseed users
python db/seed_data.py

# Try default credentials:
# Username: admin
# Password: admin123
```

### Build Fails

**Problem**: `npm run build` fails

```bash
# Common fixes:

# 1. Clear cache
rm -rf node_modules .vite dist
npm install

# 2. Check for syntax errors
npm run lint

# 3. Increase Node.js memory
NODE_OPTIONS=--max-old-space-size=4096 npm run build

# 4. Check package versions
npm outdated
```

### Vite Dev Server Crashes

**Problem**: Dev server crashes or won't start

```bash
# Kill process on port 5173
lsof -i :5173
kill -9 <PID>

# Clear Vite cache
rm -rf node_modules/.vite

# Restart dev server
npm run dev
```

---

## RabbitMQ & Celery Issues

### RabbitMQ Not Starting

**Problem**: `rabbitmq-server` command fails

```bash
# Check RabbitMQ status
# macOS
brew services list | grep rabbitmq

# Ubuntu
sudo systemctl status rabbitmq-server

# Check logs
# macOS
tail -f /opt/homebrew/var/log/rabbitmq/rabbit@*.log

# Ubuntu
sudo journalctl -u rabbitmq-server -xe

# Reset RabbitMQ (⚠️ deletes all queues!)
# macOS
brew services stop rabbitmq
rm -rf /opt/homebrew/var/lib/rabbitmq/mnesia
brew services start rabbitmq

# Ubuntu
sudo systemctl stop rabbitmq-server
sudo rm -rf /var/lib/rabbitmq/mnesia
sudo systemctl start rabbitmq-server
```

### Cannot Access Management UI

**Problem**: http://localhost:15672 not accessible

```bash
# Enable management plugin
sudo rabbitmq-plugins enable rabbitmq_management

# Restart RabbitMQ
# macOS
brew services restart rabbitmq

# Ubuntu
sudo systemctl restart rabbitmq-server

# Check if port 15672 is listening
lsof -i :15672
```

### Celery Worker Won't Start

**Problem**: `celery worker` command fails

```bash
# Check RabbitMQ connection
celery -A celery_worker.celery_app inspect ping

# Check broker URL
echo $CELERY_BROKER_URL
# Should be: amqp://guest:guest@localhost:5672//

# Verify RabbitMQ is accessible
telnet localhost 5672

# Check for Python import errors
python -c "from celery_worker import celery_app; print(celery_app)"

# Start worker with verbose logging
celery -A celery_worker.celery_app worker --loglevel=debug
```

### Tasks Not Processing

**Problem**: Tasks stuck in queue

```bash
# Check active tasks
celery -A celery_worker.celery_app inspect active

# Check reserved tasks
celery -A celery_worker.celery_app inspect reserved

# Purge all tasks (⚠️ deletes queued tasks!)
celery -A celery_worker.celery_app purge

# Check worker availability
celery -A celery_worker.celery_app inspect stats

# Restart Celery worker
pkill -f "celery worker"
celery -A celery_worker.celery_app worker --loglevel=info
```

### Celery Worker Memory Issues

**Problem**: Worker consuming too much memory

```bash
# Limit tasks per child process
celery -A celery_worker.celery_app worker --max-tasks-per-child=100

# Reduce concurrency
celery -A celery_worker.celery_app worker --concurrency=1

# Monitor memory usage
celery -A celery_worker.celery_app inspect stats
```

---

## Cloud Storage Issues

### GCP Storage Connection Failed

**Problem**: Cannot upload/download files to GCP

```bash
# Verify service account JSON
cat .env | grep CLOUD_STORAGE_SECRET

# Test GCP authentication
gcloud auth application-default print-access-token

# Check bucket permissions
gsutil ls gs://your-bucket-name

# Test from Python
python -c "
from google.cloud import storage
client = storage.Client()
print([b.name for b in client.list_buckets()])
"
```

### AWS S3 Connection Failed

**Problem**: Cannot access S3 bucket

```bash
# Verify AWS credentials
aws configure list

# Test S3 access
aws s3 ls s3://your-bucket-name

# Test from Python
python -c "
import boto3
s3 = boto3.client('s3')
print(s3.list_buckets())
"
```

### Signed URL Expired

**Problem**: `SignatureDoesNotMatch` or URL expired

```env
# Increase expiry time in .env
SIGNED_UPLOAD_URL_EXPIRY_SECONDS=1800  # 30 minutes
SIGNED_DOWNLOAD_URL_EXPIRY_SECONDS=1200  # 20 minutes
```

### File Upload Too Slow

**Problem**: Uploads timing out

```bash
# Increase timeout
# In storage_service.py
timeout = 300  # 5 minutes

# Use multipart upload for large files
# Implemented in storage_service.py for files > 5MB
```

---

## Email Notification Issues

### SMTP Authentication Failed

**Problem**: `535 Authentication failed`

```bash
# Verify SMTP credentials
echo $SMTP_USER
echo $SMTP_PASSWORD

# Test SMTP connection
python -c "
import smtplib
server = smtplib.SMTP('sandbox.smtp.mailtrap.io', 587)
server.starttls()
server.login('user', 'password')
print('✅ SMTP OK')
"

# Check SMTP logs
# Backend should show SMTP errors in console
```

### Emails Not Sending

**Problem**: Notifications not received

```bash
# Check if notifications enabled
echo $IS_NOTIFICATION_ENABLED  # Should be 'true'

# Test email service
python -c "
from services.email_service import EmailService
EmailService().send_test_email('your@email.com')
"

# Check Celery worker logs for errors
docker-compose logs celery-worker | grep email
```

### SSL/TLS Errors

**Problem**: `SSL: CERTIFICATE_VERIFY_FAILED`

```env
# Disable TLS verification (⚠️ not recommended for production)
SMTP_USE_TLS=false

# Or update CA certificates
# Ubuntu
sudo apt install ca-certificates
sudo update-ca-certificates

# macOS
brew install ca-certificates
```

---

## Performance Issues

### High CPU Usage

**Problem**: CPU usage 100%

```bash
# Check running processes
top
htop

# Identify Python processes
ps aux | grep python

# Check Celery worker concurrency
# Reduce if too high
celery -A celery_worker.celery_app worker --concurrency=1

# Profile Python code
python -m cProfile -s cumulative main.py
```

### High Memory Usage

**Problem**: RAM usage increasing over time

```bash
# Check memory usage
free -h  # Linux
vm_stat  # macOS

# Restart services
docker-compose restart backend celery-worker

# Limit Celery tasks per child
celery -A celery_worker.celery_app worker --max-tasks-per-child=50

# Enable database connection pooling
# In database.py:
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600
)
```

### Slow Database Queries

**Problem**: Queries taking too long

```sql
-- Enable query logging
-- In postgresql.conf:
log_min_duration_statement = 1000  -- Log queries > 1 second

-- Analyze slow queries
SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;

-- Add indexes
CREATE INDEX idx_executions_status ON executions(status);
CREATE INDEX idx_executions_created_at ON executions(created_at);
```

### Disk Space Full

**Problem**: `No space left on device`

```bash
# Check disk usage
df -h

# Find large directories
du -sh /* | sort -h

# Clean Docker
docker system prune -a --volumes

# Clean logs
find /var/log -type f -name "*.log" -mtime +7 -delete

# Clean uploads (⚠️ careful!)
find ./uploads -type f -mtime +30 -delete
```

---

## Docker Issues

### Container Won't Start

**Problem**: `docker-compose up` fails

```bash
# Check logs
docker-compose logs backend
docker-compose logs postgres

# Check container status
docker-compose ps

# Rebuild images
docker-compose build --no-cache

# Reset Docker
docker-compose down -v
docker system prune -a
docker-compose up -d
```

### Volume Permission Errors

**Problem**: `Permission denied` in container

```bash
# Fix ownership
sudo chown -R $(whoami):$(whoami) ./uploads ./logs

# Or in Dockerfile, run as non-root user
USER appuser
```

### Network Issues

**Problem**: Containers can't communicate

```bash
# Check network
docker network ls
docker network inspect evidence-analysis-service-p1_evidence-backend-net

# Reconnect container to network
docker network connect evidence-backend-net backend

# Use container hostnames, not localhost
# In .env:
DATABASE_URL=postgresql://user:pass@postgres:5432/db
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
```

### Image Build Fails

**Problem**: `docker build` errors

```bash
# Clear build cache
docker builder prune

# Build with verbose output
docker-compose build --progress=plain

# Build without cache
docker-compose build --no-cache
```

---

## Common Error Messages

### "Connection refused"

**Cause**: Service not running or wrong host/port

**Fix**:
```bash
# Check if service is running
sudo systemctl status postgresql
brew services list

# Verify connection details
telnet localhost 5432
curl http://localhost:8000/health
```

### "ModuleNotFoundError"

**Cause**: Missing Python dependency

**Fix**:
```bash
pip install <missing-module>
# Or reinstall all
pip install -r requirements.txt
```

### "DatabaseError: relation does not exist"

**Cause**: Database schema not initialized

**Fix**:
```bash
python db/init_db.py
alembic upgrade head
```

### "401 Unauthorized"

**Cause**: Invalid or expired JWT token

**Fix**:
```bash
# Log in again to get new token
# Or check JWT_SECRET_KEY in .env matches backend
```

### "502 Bad Gateway"

**Cause**: Backend not responding

**Fix**:
```bash
# Restart backend
docker-compose restart backend
# Or check backend logs
docker-compose logs backend
```

---

## Getting Help

If you've tried the solutions above and still have issues:

1. **Check Logs**:
   ```bash
   # Backend logs
   docker-compose logs -f backend
   
   # Celery worker logs
   docker-compose logs -f celery-worker
   
   # PostgreSQL logs
   docker-compose logs postgres
   ```

2. **Enable Debug Mode**:
   ```env
   # In .env
   DEBUG=True
   ```

3. **Collect System Info**:
   ```bash
   # System info
   uname -a
   
   # Python version
   python --version
   
   # Docker version
   docker --version
   
   # Check running services
   docker-compose ps
   ```

4. **Open an Issue**:
   - Include error messages
   - Include logs (sanitize sensitive data)
   - Include steps to reproduce
   - Include system information

---

## Quick Health Check Script

Create `health-check.sh`:

```bash
#!/bin/bash

echo "=== Evidence Analysis System Health Check ==="

# Check PostgreSQL
echo -n "PostgreSQL: "
pg_isready -h localhost -U postgres && echo "✅" || echo "❌"

# Check RabbitMQ
echo -n "RabbitMQ: "
curl -s http://localhost:15672/api/overview -u guest:guest > /dev/null && echo "✅" || echo "❌"

# Check Backend
echo -n "Backend API: "
curl -s http://localhost:8000/health > /dev/null && echo "✅" || echo "❌"

# Check Frontend
echo -n "Frontend: "
curl -s http://localhost:5173 > /dev/null && echo "✅" || echo "❌"

# Check Celery
echo -n "Celery Worker: "
celery -A celery_worker.celery_app inspect ping > /dev/null 2>&1 && echo "✅" || echo "❌"

echo "=== End Health Check ==="
```

```bash
chmod +x health-check.sh
./health-check.sh
```

---

**Still need help?** Open an issue in the repository with detailed information about your problem.
