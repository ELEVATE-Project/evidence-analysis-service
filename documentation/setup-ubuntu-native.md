# Ubuntu — Native Setup Guide

Setup without Docker on **Ubuntu 20.04 LTS, 22.04 LTS, or 24.04 LTS**.

> Looking for Docker instead? See [setup-ubuntu-docker.md](setup-ubuntu-docker.md).

---

## System Requirements

| Component | Version | Purpose |
|-----------|---------|---------|
| Ubuntu | 20.04+, 22.04+, 24.04 LTS | Operating System |
| Python | 3.12 | Backend API (FastAPI) |
| Node.js | 20 LTS | Frontend (React) & Package Manager |
| PostgreSQL | 16 | Primary Database |
| RabbitMQ | 4.3+ | Message Queue (Celery) |
| Redis | Latest | Optional Caching |
| PM2 | Latest | Optional Service Management |

---

## Prerequisites

Before setup, ensure you have:

1. **Ubuntu system**: 20.04 LTS or newer
2. **Terminal access**: Comfortable with command line
3. **sudo privileges**: Required for system package installation
4. **~30 minutes** for full setup
5. **~5GB disk space** for dependencies and data

---

## Step 1: System Update

Update system packages and install build tools:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential software-properties-common curl wget git
```

---

## Step 2: Core Installations

Install all required system dependencies:

### 2.1 Python 3.12 (Backend Runtime)

```bash
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev

python3.12 --version
```

### 2.2 Node.js 20 LTS (Frontend Runtime & NPM)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

node --version   # v20.x.x
npm --version    # 10.x.x
```

### 2.3 PostgreSQL 16 (Database)

```bash
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update
sudo apt install -y postgresql-16 postgresql-contrib-16

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Verify
psql --version
pg_isready -h localhost && echo "PostgreSQL is ready"
```

### 2.4 RabbitMQ (Message Queue for Celery)

```bash
sudo apt install -y rabbitmq-server

# Start RabbitMQ service
sudo systemctl start rabbitmq-server
sudo systemctl enable rabbitmq-server

# Verify
sudo systemctl status rabbitmq-server
```

Default credentials: **guest / guest**  
AMQP Port: **5672**  
Management UI: http://localhost:15672 (guest/guest)

### 2.5 Redis (Optional Caching)

```bash
sudo apt install -y redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server

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

Configure password authentication and create the postgres role:

```bash
# Set password for postgres user
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"

# Allow password authentication for local connections
sudo sed -i "/^local.*postgres.*peer/s/peer/md5/" /etc/postgresql/16/main/pg_hba.conf

# Restart PostgreSQL to apply changes
sudo systemctl restart postgresql

# Verify password authentication works
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

**How to get these values:**

1. **JWT_SECRET_KEY**: Generate in terminal:
   ```bash
   openssl rand -hex 32
   ```

2. **GEMINI_API_KEY_1**: 
   - Visit [Google AI Studio](https://aistudio.google.com/app/apikeys)
   - Create new API key
   - Copy the key value

3. **Cloud Storage Details**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a service account or use existing
   - Download service account JSON key
   - Copy email and JSON content

4. **SMTP Details** (Email):
   - Sign up at [Mailtrap.io](https://mailtrap.io/) (free sandbox)
   - Go to: Integrations → Nodemailer
   - Copy: Host, Port, User, Password

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

If you encounter compilation errors, install required development packages:
```bash
sudo apt install -y libpq-dev python3.12-dev build-essential
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

**Troubleshooting**: If you get `FATAL: database "evidence_analysis" does not exist`:
```bash
# Check your DATABASE_URL
grep DATABASE_URL .env

# Create database manually
createdb -U postgres -h localhost evidence_analysis

# Re-run migrations
alembic upgrade head
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
sudo systemctl status rabbitmq-server | grep -q "active (running)" && echo "✓ RabbitMQ OK"

# Check Redis (optional)
redis-cli ping && echo "✓ Redis OK"
```

### 6.2 Start Backend API

```bash
cd ~/Projects/evidence-analysis-service-p1

source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 6002
```

Expected output:
```
INFO  Starting Evidence Analysis Service...
INFO  Database migrations are current
INFO  Default seed data applied
INFO  Background worker initialized
INFO  Application startup complete.
```

> **What the Storage Bootstrap does:** On every startup the application validates cloud storage connectivity (write + read + sign a probe object), then uploads the two bundled sample CSV files (`sample_input.csv` and `sample_criteria.csv`) from `public/sample-csv/projects/` to your cloud bucket at `projects/sample_input.csv` and `projects/sample_criteria.csv`. It then records those cloud paths in the `csv_source_types` table. This is fully automatic — no manual upload is needed.
>
> **Prerequisite:** Cloud storage credentials (`CLOUD_STORAGE_PROVIDER`, `CLOUD_STORAGE_BUCKETNAME`, `CLOUD_STORAGE_ACCOUNTNAME`, `CLOUD_STORAGE_SECRET`) must be correctly set in `.env` before starting the backend. If any credential is wrong or missing the bootstrap will fail and the application will not start. See [Storage Bootstrap Issues](#storage-bootstrap-issues) in Troubleshooting.

Backend available at: http://localhost:8000

### 6.3 Start Celery Worker

```bash
# In a separate terminal
cd ~/Projects/evidence-analysis-service-p1

source venv/bin/activate
celery -A celery_worker.celery_app worker --loglevel=info --concurrency=4
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
sudo systemctl status rabbitmq-server | grep -q "active (running)" && echo "✓ RabbitMQ OK"

echo "=== Backend API ==="
curl http://localhost:6002/health | jq . && echo "✓ API OK"

echo "=== Frontend ==="
curl -s http://localhost:5173 | head -c 100 && echo "✓ Frontend OK"
```

---

## Alternative: Set Up as System Services (Optional)

For auto-start on reboot without PM2, create systemd units.

### Backend Service

```bash
sudo nano /etc/systemd/system/evidence-backend.service
```

```ini
[Unit]
Description=Evidence Analysis Backend
After=network.target postgresql.service rabbitmq-server.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/Projects/evidence-analysis-service-p1
Environment="PATH=/home/YOUR_USERNAME/Projects/evidence-analysis-service-p1/venv/bin"
ExecStart=/home/YOUR_USERNAME/Projects/evidence-analysis-service-p1/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Celery Worker Service

```bash
sudo nano /etc/systemd/system/evidence-celery.service
```

```ini
[Unit]
Description=Evidence Analysis Celery Worker
After=network.target postgresql.service rabbitmq-server.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/Projects/evidence-analysis-service-p1
Environment="PATH=/home/YOUR_USERNAME/Projects/evidence-analysis-service-p1/venv/bin"
ExecStart=/home/YOUR_USERNAME/Projects/evidence-analysis-service-p1/venv/bin/celery -A celery_worker.celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable evidence-backend evidence-celery
sudo systemctl start evidence-backend evidence-celery

# Verify
sudo systemctl status evidence-backend evidence-celery
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

**Error: `psql: error: FATAL: password authentication failed`**
```bash
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
sudo sed -i "/^local.*postgres.*peer/s/peer/md5/" /etc/postgresql/16/main/pg_hba.conf
sudo systemctl restart postgresql
```

**Error: `FATAL: role "postgres" does not exist`**
```bash
sudo -u postgres createuser --superuser postgres
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
sudo systemctl restart postgresql
```

### PostgreSQL Connection Issues

**Error: `could not connect to server: Connection refused`**
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Start if not running
sudo systemctl start postgresql

# Verify connection
psql -U postgres -h localhost -c "SELECT 1;"
```

### Python/Dependencies Issues

**Error: `pg_config not found`**
```bash
sudo apt install -y libpq-dev python3.12-dev
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

### RabbitMQ Issues

**Error: `Connection refused` to RabbitMQ**
```bash
# Check status
sudo systemctl status rabbitmq-server

# Restart if needed
sudo systemctl restart rabbitmq-server
```

**RabbitMQ won't start**
```bash
sudo journalctl -u rabbitmq-server -xe
sudo systemctl stop rabbitmq-server
sudo rm -rf /var/lib/rabbitmq/mnesia
sudo systemctl start rabbitmq-server
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
3. Verify all services running: `pm2 status` or `sudo systemctl status postgresql rabbitmq-server`
4. Ensure all dependencies installed: `pip list` and `npm list -g pm2`
