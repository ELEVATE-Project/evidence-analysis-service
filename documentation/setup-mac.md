# macOS Setup Guide - Evidence Analysis System

This guide provides step-by-step instructions for setting up the Evidence Analysis System on **macOS** (Monterey 12.0+, Ventura 13.0+, Sonoma 14.0+).

---

## Prerequisites

- macOS 12.0 (Monterey) or higher
- Administrator access (sudo privileges)
- Xcode Command Line Tools
- Homebrew package manager

---

## Step 1: Install Homebrew

If you don't have Homebrew installed:

```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Verify installation
brew --version
```

---

## Step 2: Install Core Dependencies

### 2.1 Install Python 3.12

```bash
# Install Python 3.12
brew install python@3.12

# Verify installation
python3.12 --version

# Create symlink (optional)
brew link python@3.12

# Verify pip
pip3 --version
```

### 2.2 Install Node.js and npm

```bash
# Install Node.js (LTS version)
brew install node@20

# Verify installation
node --version  # Should be v20.x.x
npm --version   # Should be 10.x.x
```

### 2.3 Install PostgreSQL

```bash
# Install PostgreSQL 16
brew install postgresql@16

# Start PostgreSQL service
brew services start postgresql@16

# Verify installation
psql --version

# Create default database user and database
createuser -s postgres  # Create superuser
createdb evidence_analysis  # Create database

# Test connection
psql -U postgres -d evidence_analysis -c "SELECT version();"
```

**Alternative**: Use Postgres.app (GUI application)
```bash
# Download from: https://postgresapp.com/
# Drag to Applications folder
# Open and click "Initialize"
```

### 2.4 Install RabbitMQ

```bash
# Install RabbitMQ
brew install rabbitmq

# Add RabbitMQ to PATH (add to ~/.zshrc or ~/.bash_profile)
echo 'export PATH="/opt/homebrew/opt/rabbitmq/sbin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Start RabbitMQ service
brew services start rabbitmq

# Verify installation
rabbitmq-diagnostics ping

# Access management UI
open http://localhost:15672
# Login: guest / guest
```

### 2.5 Install Redis (Optional)

```bash
# Install Redis
brew install redis

# Start Redis service
brew services start redis

# Verify installation
redis-cli ping  # Should return "PONG"
```

### 2.6 Install Git

```bash
# Install Git
brew install git

# Verify installation
git --version

# Configure Git
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

---

## Step 3: Clone Repository

```bash
# Navigate to your projects directory
cd ~/Projects  # Or your preferred location

# Clone repository
git clone <repository-url>
cd evidence-analysis-service-p1
```

---

## Step 4: Backend Setup

### 4.1 Create Virtual Environment

```bash
# Navigate to backend directory
cd evidence-analysis-service-p1

# Create virtual environment
python3.12 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### 4.2 Install Python Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep fastapi
pip list | grep celery
pip list | grep sqlalchemy
```

### 4.3 Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit environment file
nano .env  # Or use your preferred editor (vim, code, etc.)
```

**Required Environment Variables** (see [environment-setup.md](environment-setup.md) for full list):

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/evidence_analysis

# JWT (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your-generated-secret-key-here
JWT_ALGORITHM=HS256

# CORS
CORS_ORIGINS=["http://localhost:5173"]

# Gemini AI
GEMINI_API_KEY_1=your-gemini-api-key

# Cloud Storage (GCP or AWS)
CLOUD_STORAGE_PROVIDER=gcp
CLOUD_STORAGE_BUCKETNAME=your-bucket-name
# ... (add your cloud storage credentials)

# Celery/RabbitMQ
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//

# SMTP
IS_NOTIFICATION_ENABLED=true
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=your-mailtrap-user
SMTP_PASSWORD=your-mailtrap-password
```

### 4.4 Initialize Database

```bash
# Ensure PostgreSQL is running
brew services list | grep postgresql

# Initialize database schema
python db/init_db.py

# Seed default users
python db/seed_data.py

# Run migrations
alembic upgrade head

# Verify database
psql -U postgres -d evidence_analysis -c "\dt"
```

### 4.5 Start Backend Server

```bash
# In terminal 1: Start FastAPI server
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# API will be available at:
# - http://localhost:8000
# - http://localhost:8000/docs (Swagger UI)
```

### 4.6 Start Celery Worker

```bash
# In terminal 2: Start Celery worker
cd evidence-analysis-service-p1
source venv/bin/activate
celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2
```

---

## Step 5: Frontend Setup

### 5.1 Navigate to Frontend Directory

```bash
# Open new terminal
cd ~/Projects/evidence-analysis-portal-p1  # Adjust path as needed
```

### 5.2 Install Dependencies

```bash
# Install npm dependencies
npm install

# Verify installation
npm list react
npm list vite
```

### 5.3 Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit if needed (defaults should work)
nano .env
```

**Default Frontend Configuration**:
```env
APPLICATION_PORT=5173
APPLICATION_BASE_URL=/api/v1
API_ENDPOINT=http://localhost:8000
```

### 5.4 Start Development Server

```bash
# Start Vite dev server
npm run dev

# Frontend will be available at:
# http://localhost:5173
```

---

## Step 6: Verify Installation

### 6.1 Check Backend Health

```bash
# Test API health endpoint
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"1.0.0"}

# Test Swagger UI
open http://localhost:8000/docs
```

### 6.2 Check Database Connection

```bash
# Connect to database
psql -U postgres -d evidence_analysis

# List tables
\dt

# Check users table
SELECT username FROM users;

# Exit
\q
```

### 6.3 Check RabbitMQ

```bash
# Check RabbitMQ status
brew services list | grep rabbitmq

# Access management UI
open http://localhost:15672
# Login: guest / guest
# Verify "execution_queue" exists in Queues tab
```

### 6.4 Check Frontend

```bash
# Open frontend in browser
open http://localhost:5173

# Try logging in:
# Username: admin
# Password: admin123
```

### 6.5 End-to-End Test

1. **Login** at http://localhost:5173
2. **Navigate** to "New Execution"
3. **Upload** a sample CSV file
4. **Submit** for processing
5. **Monitor** execution status
6. **Download** results when complete

---

## Troubleshooting

### Python Version Issues

```bash
# If python3.12 not found
brew install python@3.12
brew link python@3.12

# Use python3 explicitly
python3 --version
```

### PostgreSQL Connection Failed

```bash
# Check if PostgreSQL is running
brew services list

# Restart PostgreSQL
brew services restart postgresql@16

# Check port
lsof -i :5432

# Reset password if needed
psql postgres
ALTER USER postgres PASSWORD 'postgres';
```

### RabbitMQ Not Starting

```bash
# Check logs
tail -f /opt/homebrew/var/log/rabbitmq/rabbit@*.log

# Restart service
brew services restart rabbitmq

# Reset if corrupted
brew services stop rabbitmq
rm -rf /opt/homebrew/var/lib/rabbitmq/mnesia
brew services start rabbitmq
```

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>
```

### Permission Denied Errors

```bash
# Fix ownership
sudo chown -R $(whoami) /opt/homebrew
sudo chown -R $(whoami) ~/Library/Caches/Homebrew

# Fix permissions in project
chmod +x venv/bin/activate
```

### Node.js / npm Issues

```bash
# Clear npm cache
npm cache clean --force

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

---

## Uninstall / Cleanup

```bash
# Stop services
brew services stop postgresql@16
brew services stop rabbitmq
brew services stop redis

# Uninstall packages
brew uninstall postgresql@16 rabbitmq redis python@3.12 node@20

# Remove data directories
rm -rf ~/Library/Application\ Support/Postgres
rm -rf /opt/homebrew/var/lib/rabbitmq
rm -rf /opt/homebrew/var/lib/redis

# Remove project
rm -rf ~/Projects/evidence-analysis-*
```

---

## Service Management Scripts

### Start All Services

```bash
# Create start script
cat > start-services.sh << 'EOF'
#!/bin/bash
echo "Starting PostgreSQL..."
brew services start postgresql@16
echo "Starting RabbitMQ..."
brew services start rabbitmq
echo "Starting Redis..."
brew services start redis
echo "All services started!"
EOF

chmod +x start-services.sh
./start-services.sh
```

### Stop All Services

```bash
# Create stop script
cat > stop-services.sh << 'EOF'
#!/bin/bash
echo "Stopping PostgreSQL..."
brew services stop postgresql@16
echo "Stopping RabbitMQ..."
brew services stop rabbitmq
echo "Stopping Redis..."
brew services stop redis
echo "All services stopped!"
EOF

chmod +x stop-services.sh
./stop-services.sh
```

---

## Next Steps

- [ ] Review [Environment Setup Guide](environment-setup.md)
- [ ] Configure cloud storage credentials
- [ ] Set up email notifications
- [ ] Review [Troubleshooting Guide](troubleshooting.md)
- [ ] Customize application settings
- [ ] Set up monitoring and logging

---

## Additional Resources

- [Homebrew Documentation](https://docs.brew.sh/)
- [PostgreSQL macOS Installation](https://www.postgresql.org/download/macosx/)
- [Node.js macOS Installation](https://nodejs.org/en/download/)
- [Python macOS Setup Guide](https://docs.python-guide.org/starting/install3/osx/)

---

**Need Help?** See the [Troubleshooting Guide](troubleshooting.md) or open an issue in the repository.
