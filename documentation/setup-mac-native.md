# macOS — Native Setup Guide

Setup without Docker on **macOS Monterey 12.0+, Ventura 13.0+, or Sonoma 14.0+**.

> Looking for Docker instead? See [setup-mac-docker.md](setup-mac-docker.md).

---

## System Requirements

| Component | Version | Purpose |
|-----------|---------|---------|
| macOS | 12.0+ (Monterey, Ventura, Sonoma) | Operating System |
| Python | 3.12 | Backend API (FastAPI) |
| Node.js | 20 LTS | Frontend (React) & Package Manager |
| PostgreSQL | 16 | Primary Database |
| RabbitMQ | 4.3+ | Message Queue (Celery) |
| Redis | Latest | Optional Caching |
| PM2 | Latest | Optional Service Management |

---

## Prerequisites

Before setup, ensure you have:

1. **Homebrew installed**: macOS package manager
2. **Terminal access**: Comfortable with command line
3. **~30 minutes** for full setup
4. **~5GB disk space** for dependencies and data

---

## Step 1: Install Homebrew (if not already installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Follow any post-install instructions (e.g., adding Homebrew to PATH on Apple Silicon)
brew --version
```

---

## Step 2: Core Installations

Install all required system dependencies:

### 2.1 Python 3.12 (Backend Runtime)

```bash
brew install python@3.12
python3.12 --version
```

### 2.2 Node.js 20 LTS (Frontend Runtime & NPM)

```bash
brew install node@20

# Add to PATH if on Apple Silicon
echo 'export PATH="/opt/homebrew/opt/node@20/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

node --version   # v20.x.x
npm --version    # 10.x.x
```

### 2.3 PostgreSQL 16 (Database)

```bash
brew install postgresql@16

# Add PostgreSQL to PATH
echo 'export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Start PostgreSQL service
brew services start postgresql@16

# Verify
psql --version
pg_isready && echo "PostgreSQL is ready"
```

### 2.4 RabbitMQ (Message Queue for Celery)

```bash
brew install rabbitmq

# Start RabbitMQ service
brew services start rabbitmq

# Verify
brew services list | grep rabbitmq
```

Default credentials: **guest / guest**  
AMQP Port: **5672**  
Management UI: http://localhost:15672 (guest/guest)

### 2.5 Redis (Optional Caching)

```bash
brew install redis
brew services start redis

# Verify
redis-cli ping   # Should return: PONG
```

### 2.6 PM2 (Optional - for Production-like Service Management)

```bash
npm install -g pm2
pm2 --version
```

---

## Step 3: Setting up PostgreSQL

Create the `postgres` role to match the `DATABASE_URL` format in configuration:

```bash
# Create postgres user (if it doesn't exist)
createuser -s postgres 2>/dev/null || echo "postgres role already exists"

# Set password for postgres user
psql postgres -c "ALTER USER postgres PASSWORD 'postgres';"

# Verify authentication works
psql -U postgres -h localhost -c "SELECT version();" && echo "PostgreSQL auth OK"
```

---

## Step 4: Setting up Repository

### 4.1 Clone the Repository

```bash
mkdir -p ~/Projects
cd ~/Projects

git clone <repository-url>
cd evidence-analysis-service-p1
```

### 4.2 Attach Configuration File

```bash
# Copy environment template
cp .env.example .env
```

### 4.3 Update Environment Configuration

Before proceeding with dependency installation, you **must** configure the required environment variables.

Edit `.env` file:
```bash
nano .env
```

**Update the following required keys:**

| Key | Description | Example |
|-----|-------------|---------|
| `JWT_SECRET_KEY` | Generate with: `openssl rand -hex 32` | `a1b2c3d4e5f6...` |
| `GEMINI_API_KEY_1` | Google Gemini API key for AI features | `AIzaSyD...` |
| `CLOUD_STORAGE_PROVIDER` | Cloud storage provider | `gcp` |
| `CLOUD_STORAGE_BUCKETNAME` | GCS bucket name | `my-evidence-bucket` |
| `CLOUD_STORAGE_ACCOUNTNAME` | Service account email | `sa@project.iam.gserviceaccount.com` |
| `CLOUD_STORAGE_SECRET` | Service account JSON key | `{...json...}` |
| `SMTP_HOST` | Email service host | `sandbox.smtp.mailtrap.io` |
| `SMTP_PORT` | Email service port | `587` |
| `SMTP_USER` | Email service username | `mailtrap-user` |
| `SMTP_PASSWORD` | Email service password | `mailtrap-password` |

**Required environment variables template:**

```env
# ============================================================
# DATABASE
# ============================================================
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/evidence_analysis

# ============================================================
# AUTHENTICATION & SECURITY
# ============================================================
JWT_SECRET_KEY=<GENERATE: openssl rand -hex 32>
CORS_ORIGINS=["http://localhost:5173"]

# ============================================================
# AI/ML SERVICES
# ============================================================
GEMINI_API_KEY_1=<YOUR_GEMINI_API_KEY>

# ============================================================
# CLOUD STORAGE (Google Cloud)
# ============================================================
CLOUD_STORAGE_PROVIDER=gcp
CLOUD_STORAGE_BUCKETNAME=<YOUR_GCS_BUCKET_NAME>
CLOUD_STORAGE_ACCOUNTNAME=<SERVICE_ACCOUNT_EMAIL>
CLOUD_STORAGE_SECRET=<SERVICE_ACCOUNT_JSON_KEY>

# ============================================================
# MESSAGE QUEUE (Celery)
# ============================================================
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//

# ============================================================
# EMAIL NOTIFICATIONS (SMTP)
# ============================================================
IS_NOTIFICATION_ENABLED=true
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=<YOUR_SMTP_USER>
SMTP_PASSWORD=<YOUR_SMTP_PASSWORD>
```

**Save the file**: Press `Ctrl+X` → `Y` → `Enter` (in nano)

---

### 4.4 Install Backend Dependencies

```bash
# Create Python virtual environment
python3.12 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip and install build tools
pip install --upgrade pip wheel

# Install all Python dependencies
pip install -r requirements.txt
```

If you encounter `pg_config not found` error:
```bash
pip install psycopg2-binary
pip install -r requirements.txt
```

---

## Step 5: Database Setup

### 5.1 Create Database

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Create the database
python scripts/create_dev_db.py
```

This script:
- Reads `DATABASE_URL` from `.env`
- Creates the database if it doesn't exist
- Is safe to re-run (idempotent)

### 5.2 Run Migrations

```bash
# Apply all pending Alembic migrations
alembic upgrade head

# Verify migrations are current
alembic current
```

### 5.3 Seed Default Data

```bash
# Seed default users and CSV source type configuration
python db/seed_data.py
```

This script:
- Creates the three default users (`admin`, `program_designer`, `analyst`) with bcrypt-hashed passwords
- Creates the default `project_report` CSV source type configuration
- Is safe to re-run (idempotent — skips records that already exist)

> **Why this is a separate step:** The application also seeds on startup automatically (via FastAPI lifespan), but that requires cloud storage to be fully configured first. Running the seed script here ensures your database has the required data regardless of cloud storage status, and lets you verify the database state before starting the application.

---

## Step 6: Backend Service Setup

### 6.1 Verify Services are Running

```bash
# Check PostgreSQL
pg_isready -h localhost && echo "✓ PostgreSQL OK"

# Check RabbitMQ
curl -s -u guest:guest http://localhost:15672/api/overview \
  | grep -q '"status":"ok"' && echo "✓ RabbitMQ OK"

# Check Redis (optional)
redis-cli ping && echo "✓ Redis OK"
```

### 6.2 Start Backend API

```bash
# Terminal 1
cd ~/Projects/evidence-analysis-service-p1

source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO  Starting Evidence Analysis Service...
INFO  Database migrations are current
INFO  Default seed data applied
INFO  Background worker initialized
INFO  Application startup complete.
```

Backend available at: http://localhost:8000

### 6.3 Start Celery Worker

```bash
# Terminal 2 (separate terminal with venv activated)
cd ~/Projects/evidence-analysis-service-p1

source venv/bin/activate
celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2
```

**Concurrency Settings:**
- `--concurrency=2`: Light workload, shared machine
- `--concurrency=4`: Balanced (default), 50K rows ≈ 7 hours
- `--concurrency=6-8`: Dedicated machine, 50K rows ≈ 4-5 hours
- `--concurrency=12+`: Cloud server, 50K rows ≈ 2-3 hours

---

## Step 7: Frontend Service Setup

### 7.1 Install Frontend Dependencies

```bash
# Terminal 3
cd ~/Projects/evidence-analysis-portal-p1

cp .env.example .env
nano .env
```

Update `.env` if needed (default config usually works):
```env
VITE_API_BASE_URL=http://localhost:8000
```

### 7.2 Start Frontend Development Server

```bash
npm install
npm run dev
```

Frontend available at: http://localhost:5173

---

## Step 8: Start All Services with PM2

PM2 is a production process manager that keeps services running, auto-restarts them on failure, and persists across terminal sessions.

### 8.1 Start Individual Services

**Start Backend API:**
```bash
cd ~/Projects/evidence-analysis-service-p1
source venv/bin/activate
pm2 start uvicorn --cwd ~/Projects/evidence-analysis-service-p1 --name evidence-backend -- main:app --host 0.0.0.0 --port 8000
```

**Start Celery Worker:**
```bash
cd ~/Projects/evidence-analysis-service-p1
source venv/bin/activate
pm2 start celery --cwd ~/Projects/evidence-analysis-service-p1 --name celery-worker -- -A celery_worker.celery_app worker --loglevel=info --concurrency=4
```

**Start Frontend:**
```bash
cd ~/Projects/evidence-analysis-portal-p1
pm2 start npm --cwd ~/Projects/evidence-analysis-portal-p1 --name frontend -- run dev
```

### 8.2 Verify Services Started

```bash
pm2 status
```

Expected output:
```
┌──────────────────┬────┬─────────┬──────┬────────┐
│ Name             │ id │ mode    │ ↺    │ status │
├──────────────────┼────┼─────────┼──────┼────────┤
│ evidence-backend │ 0  │ fork    │ 0    │ online │
│ celery-worker    │ 1  │ fork    │ 0    │ online │
│ frontend         │ 2  │ fork    │ 0    │ online │
└──────────────────┴────┴─────────┴──────┴────────┘
```

### 8.3 Alternative: Start All Services at Once

Alternatively, use the ecosystem JSON configuration file to start all services together:

```bash
pm2 start ~/Projects/evidence-analysis-service-p1/documentation/ecosystem.json
```

### 8.4 Monitor Services

```bash
# Dashboard view with memory, CPU, uptime
pm2 monit

# View all service logs
pm2 logs

# View specific service logs
pm2 logs evidence-backend     # Backend logs
pm2 logs celery-worker        # Celery worker logs
pm2 logs frontend             # Frontend logs

# View logs in real-time (last 10 lines)
pm2 logs celery-worker --lines 10
```

### 8.5 Service Management Commands

```bash
# Restart a specific service
pm2 restart evidence-backend
pm2 restart celery-worker
pm2 restart frontend

# Restart all services
pm2 restart all

# Stop a specific service
pm2 stop celery-worker

# Stop all services
pm2 stop all

# Get detailed info about a service
pm2 show celery-worker

# Remove a service from PM2
pm2 delete celery-worker

# Remove all services
pm2 delete all
```

### 8.6 Adjust Celery Concurrency

To change concurrency for different workloads:

```bash
# Kill the current celery worker
pm2 delete celery-worker

# Start with new concurrency value
# Example: for faster processing (6 concurrency instead of 4)
pm2 start celery --cwd ~/Projects/evidence-analysis-service-p1 --name celery-worker -- -A celery_worker.celery_app worker --loglevel=info --concurrency=6

# Verify it's running
pm2 status
```

**Concurrency Guidelines:**
- `--concurrency=2`: Light workload, shared machine
- `--concurrency=4`: Balanced (default), 50K rows ≈ 7 hours
- `--concurrency=6-8`: Dedicated machine, 50K rows ≈ 4-5 hours
- `--concurrency=12+`: Cloud server, 50K rows ≈ 2-3 hours

### 8.7 Auto-start Services on System Reboot

```bash
# Generate startup script
pm2 startup

# Save current PM2 process list
pm2 save

# Verify setup
pm2 ls
```

### 8.8 Stop All Services

```bash
# Stop all services (they won't restart)
pm2 stop all

# Delete all services from PM2
pm2 delete all
```

---

## Step 9: Verification

### 9.1 API Health Check

```bash
curl http://localhost:6002/health
# Expected: {"status":"healthy","version":"1.0.0"}
```

### 9.2 Database Verification

```bash
# Check tables exist
psql -U postgres -h localhost -d evidence_analysis -c "\dt"

# Check migrations applied
psql -U postgres -h localhost -d evidence_analysis -c "\d alembic_version"
```

### 9.3 Frontend Access

Open http://localhost:5173 in your browser.

**Default credentials:**
- Username: `admin`
- Password: `admin123`

### 9.4 Full System Test

```bash
echo "=== PostgreSQL ==="
pg_isready -h localhost && echo "✓ PostgreSQL OK"

echo "=== RabbitMQ ==="
curl -s -u guest:guest http://localhost:15672/api/overview \
  | grep -q '"status":"ok"' && echo "✓ RabbitMQ OK"

echo "=== Backend API ==="
curl http://localhost:6002/health | jq . && echo "✓ API OK"

echo "=== Frontend ==="
curl -s http://localhost:5173 | head -c 100 && echo "✓ Frontend OK"
```

---

## Troubleshooting

### Database Issues

**Error: `FATAL: database "evidence_analysis" does not exist`**
```bash
# Check DATABASE_URL
grep DATABASE_URL .env

# Create database manually
createdb -U postgres -h localhost evidence_analysis

# Run migrations
alembic upgrade head
```

**Error: `psql: error: FATAL: Ident authentication failed`**
```bash
# Verify postgres user exists and password is set
createuser -s postgres 2>/dev/null || echo "User exists"
psql postgres -c "ALTER USER postgres PASSWORD 'postgres';"

# Test connection
psql -U postgres -h localhost -c "SELECT 1;"
```

### Python/Dependencies Issues

**Error: `pg_config not found`**
```bash
pip install psycopg2-binary
pip install -r requirements.txt
```

**Error: `ModuleNotFoundError: No module named 'pandas'`**
```bash
# Verify venv is activated
which python  # Should show venv/bin/python

# Reinstall requirements
pip install -r requirements.txt
```

### Service Connection Issues

**Error: `Connection refused` on port 8000**
```bash
# Check if backend is running
lsof -i :8000

# Check for port conflicts
lsof -i :5672 :15672 :5173
```

**Error: `Connection refused` on RabbitMQ**
```bash
# Verify RabbitMQ is running
brew services list | grep rabbitmq

# Restart if needed
brew services restart rabbitmq
```

### PM2 Issues

**Services not starting with PM2:**
```bash
pm2 logs  # Check error logs
pm2 show celery-worker  # Detailed service info
```

**PM2 services crashing due to memory:**
```bash
pm2 monit  # Check memory usage
# Reduce celery concurrency if high memory:
# Edit documentation/ecosystem.json and change --concurrency value
pm2 restart celery-worker
```

### Login / Seed Data Issues

**Users table empty / login fails**
```bash
# Run the seed script directly — this is the recommended fix:
source venv/bin/activate
python db/seed_data.py
```

The application also seeds on startup, but only after cloud storage validation succeeds.
If cloud storage is not yet configured, the app may fail to start before seeding occurs.
Running `python db/seed_data.py` seeds the database independently of cloud storage.

---

## Next Steps

1. **Environment Variables**: Complete all configuration in `.env`
2. **API Documentation**: Visit http://localhost:6002/docs (Swagger UI)
3. **Frontend Development**: See [Frontend Setup Guide](../frontend-setup.md)
4. **Production Deployment**: See [Production Deployment Guide](../production-deployment.md)

---

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section above
2. Review service logs: `pm2 logs` or terminal output
3. Verify all services running: `pm2 status` or `lsof -i :8000 :5173 :5672`
4. Ensure all dependencies installed: `pip list` and `npm list -g pm2`
