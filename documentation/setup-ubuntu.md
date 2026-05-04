# Ubuntu Setup Guide - Evidence Analysis System

This guide provides step-by-step instructions for setting up the Evidence Analysis System on **Ubuntu** (20.04 LTS, 22.04 LTS, 24.04 LTS).

---

## Prerequisites

- Ubuntu 20.04 LTS or higher
- Sudo privileges
- Internet connection

---

## Step 1: Update System

```bash
# Update package lists
sudo apt update
sudo apt upgrade -y

# Install essential build tools
sudo apt install -y build-essential software-properties-common curl wget git
```

---

## Step 2: Install Core Dependencies

### 2.1 Install Python 3.12

```bash
# Add deadsnakes PPA for Python 3.12
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# Install Python 3.12 and pip
sudo apt install -y python3.12 python3.12-venv python3.12-dev python3-pip

# Verify installation
python3.12 --version
pip3 --version

# Set Python 3.12 as alternative (optional)
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
```

### 2.2 Install Node.js and npm

```bash
# Install Node.js 20 LTS using NodeSource repository
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify installation
node --version  # Should be v20.x.x
npm --version   # Should be 10.x.x

# Alternative: Using nvm (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20
```

### 2.3 Install PostgreSQL

```bash
# Install PostgreSQL 16
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update
sudo apt install -y postgresql-16 postgresql-contrib-16

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Verify installation
sudo systemctl status postgresql
psql --version

# Configure PostgreSQL
sudo -u postgres psql

# In psql prompt, run:
ALTER USER postgres PASSWORD 'postgres';
CREATE DATABASE evidence_analysis;
\q

# Test connection
psql -U postgres -h localhost -d evidence_analysis -c "SELECT version();"
```

**Configure PostgreSQL Authentication**:

```bash
# Edit pg_hba.conf to allow password authentication
sudo nano /etc/postgresql/16/main/pg_hba.conf

# Change this line:
# local   all             postgres                                peer

# To:
# local   all             postgres                                md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### 2.4 Install RabbitMQ

```bash
# Install Erlang (RabbitMQ dependency)
sudo apt install -y erlang

# Add RabbitMQ repository
curl -fsSL https://packagecloud.io/rabbitmq/rabbitmq-server/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/rabbitmq-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/rabbitmq-archive-keyring.gpg] https://packagecloud.io/rabbitmq/rabbitmq-server/ubuntu/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/rabbitmq.list

# Install RabbitMQ
sudo apt update
sudo apt install -y rabbitmq-server

# Start RabbitMQ service
sudo systemctl start rabbitmq-server
sudo systemctl enable rabbitmq-server

# Verify installation
sudo systemctl status rabbitmq-server

# Enable management plugin
sudo rabbitmq-plugins enable rabbitmq_management

# Create admin user (optional)
sudo rabbitmqctl add_user admin admin123
sudo rabbitmqctl set_user_tags admin administrator
sudo rabbitmqctl set_permissions -p / admin ".*" ".*" ".*"

# Access management UI
http://localhost:15672
# Login: guest / guest (or admin / admin123)
```

### 2.5 Install Redis (Optional)

```bash
# Install Redis
sudo apt install -y redis-server

# Start Redis service
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Verify installation
redis-cli ping  # Should return "PONG"

# Check status
sudo systemctl status redis-server
```

### 2.6 Install Git

```bash
# Install Git
sudo apt install -y git

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
cd ~
mkdir -p Projects
cd Projects

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

# Install wheel for binary packages
pip install wheel
```

### 4.2 Install Python Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# If you encounter compilation errors, install development headers:
sudo apt install -y libpq-dev python3.12-dev

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
nano .env  # Or use vim, gedit, or your preferred editor
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
# Ensure virtual environment is activated
source venv/bin/activate

# Ensure PostgreSQL is running
sudo systemctl status postgresql

# Initialize database schema
python db/init_db.py

# Seed default users
python db/seed_data.py

# Run migrations
alembic upgrade head

# Verify database
psql -U postgres -h localhost -d evidence_analysis -c "\dt"
```

### 4.5 Start Backend Server

```bash
# In terminal 1: Start FastAPI server
cd evidence-analysis-service-p1
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

# If you encounter permission errors:
sudo chown -R $(whoami) ~/.npm
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
xdg-open http://localhost:8000/docs  # Or manually open in browser
```

### 6.2 Check Database Connection

```bash
# Connect to database
psql -U postgres -h localhost -d evidence_analysis

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
sudo systemctl status rabbitmq-server

# List queues
sudo rabbitmqctl list_queues

# Access management UI
xdg-open http://localhost:15672
# Login: guest / guest
```

### 6.4 Check Frontend

```bash
# Open frontend in browser
xdg-open http://localhost:5173

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

## Step 7: Set Up as System Services (Optional)

### 7.1 Create Systemd Service for Backend

```bash
# Create service file
sudo nano /etc/systemd/system/evidence-backend.service
```

**Add the following content**:

```ini
[Unit]
Description=Evidence Analysis Backend API
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

**Replace `YOUR_USERNAME` with your actual username**, then:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable evidence-backend
sudo systemctl start evidence-backend

# Check status
sudo systemctl status evidence-backend
```

### 7.2 Create Systemd Service for Celery Worker

```bash
# Create service file
sudo nano /etc/systemd/system/evidence-celery.service
```

**Add the following content**:

```ini
[Unit]
Description=Evidence Analysis Celery Worker
After=network.target postgresql.service rabbitmq-server.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/Projects/evidence-analysis-service-p1
Environment="PATH=/home/YOUR_USERNAME/Projects/evidence-analysis-service-p1/venv/bin"
ExecStart=/home/YOUR_USERNAME/Projects/evidence-analysis-service-p1/venv/bin/celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Replace `YOUR_USERNAME` with your actual username**, then:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable evidence-celery
sudo systemctl start evidence-celery

# Check status
sudo systemctl status evidence-celery
```

---

## Troubleshooting

### Python Module Import Errors

```bash
# Reinstall dependencies
pip install --upgrade --force-reinstall -r requirements.txt

# Install development headers if compilation fails
sudo apt install -y libpq-dev python3.12-dev build-essential
```

### PostgreSQL Connection Failed

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Restart PostgreSQL
sudo systemctl restart postgresql

# Check port
sudo netstat -tuln | grep 5432

# View logs
sudo tail -f /var/log/postgresql/postgresql-16-main.log

# Reset password
sudo -u postgres psql
ALTER USER postgres PASSWORD 'postgres';
\q
```

### RabbitMQ Not Starting

```bash
# Check logs
sudo journalctl -u rabbitmq-server -xe

# Restart service
sudo systemctl restart rabbitmq-server

# Reset if corrupted
sudo systemctl stop rabbitmq-server
sudo rm -rf /var/lib/rabbitmq/mnesia
sudo systemctl start rabbitmq-server
```

### Port Already in Use

```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill process
sudo kill -9 <PID>

# Alternatively, use a different port
uvicorn main:app --port 8001
```

### Permission Denied Errors

```bash
# Fix ownership of project directory
sudo chown -R $(whoami):$(whoami) ~/Projects/evidence-analysis-*

# Fix npm permissions
sudo chown -R $(whoami) ~/.npm
```

### Firewall Issues

```bash
# Allow ports through UFW
sudo ufw allow 8000/tcp
sudo ufw allow 5173/tcp
sudo ufw allow 5432/tcp
sudo ufw allow 15672/tcp

# Check firewall status
sudo ufw status
```

### Node.js / npm Issues

```bash
# Clear npm cache
npm cache clean --force

# Remove and reinstall
rm -rf node_modules package-lock.json
npm install

# If permission errors persist
sudo chown -R $(whoami) ~/.npm
sudo chown -R $(whoami) ~/.config
```

---

## Uninstall / Cleanup

```bash
# Stop services
sudo systemctl stop evidence-backend evidence-celery
sudo systemctl disable evidence-backend evidence-celery

# Stop system services
sudo systemctl stop postgresql rabbitmq-server redis-server

# Remove packages
sudo apt remove --purge postgresql-16 rabbitmq-server redis-server
sudo apt autoremove -y

# Remove data directories
sudo rm -rf /var/lib/postgresql
sudo rm -rf /var/lib/rabbitmq
sudo rm -rf /var/lib/redis

# Remove project
rm -rf ~/Projects/evidence-analysis-*

# Remove service files
sudo rm /etc/systemd/system/evidence-*.service
sudo systemctl daemon-reload
```

---

## Service Management Scripts

### Start All Services

```bash
# Create start script
cat > start-services.sh << 'EOF'
#!/bin/bash
echo "Starting PostgreSQL..."
sudo systemctl start postgresql
echo "Starting RabbitMQ..."
sudo systemctl start rabbitmq-server
echo "Starting Redis..."
sudo systemctl start redis-server
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
sudo systemctl stop postgresql
echo "Stopping RabbitMQ..."
sudo systemctl stop rabbitmq-server
echo "Stopping Redis..."
sudo systemctl stop redis-server
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
- [ ] Set up system services for auto-start
- [ ] Configure Nginx reverse proxy (for production)
- [ ] Set up monitoring and logging

---

## Additional Resources

- [Ubuntu Server Guide](https://ubuntu.com/server/docs)
- [PostgreSQL Ubuntu Installation](https://www.postgresql.org/download/linux/ubuntu/)
- [Node.js Ubuntu Installation](https://nodejs.org/en/download/package-manager/)
- [Python Ubuntu Setup](https://docs.python-guide.org/starting/install3/linux/)
- [Systemd Service Management](https://www.freedesktop.org/software/systemd/man/systemd.service.html)

---

**Need Help?** See the [Troubleshooting Guide](troubleshooting.md) or open an issue in the repository.
