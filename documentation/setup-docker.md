# Docker Setup Guide - Evidence Analysis System

This guide provides instructions for running the Evidence Analysis System using **Docker and Docker Compose**. This is the **recommended approach** for production deployments and local development.

---

## Prerequisites

- **Docker**: 20.10+ ([Install Docker](https://docs.docker.com/get-docker/))
- **Docker Compose**: 2.0+ ([Install Compose](https://docs.docker.com/compose/install/))
- **Git**: For cloning the repository
- Minimum 4GB RAM, 10GB disk space

### Operating System Support

- **macOS**: Docker Desktop for Mac
- **Ubuntu/Linux**: Docker Engine + Docker Compose Plugin
- **Windows**: Docker Desktop for Windows (with WSL2)

---

## Quick Start (One Command)

```bash
# Clone repository
git clone <repository-url>
cd evidence-analysis-service-p1

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Start all services
docker-compose up -d

# Initialize database (first-time only)
docker-compose exec backend python db/init_db.py
docker-compose exec backend python db/seed_data.py
docker-compose exec backend alembic upgrade head
```

**Access Services:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- RabbitMQ Management: http://localhost:15672 (guest/guest)
- PostgreSQL: localhost:5432 (evidence_user/evidence_password)

---

## Detailed Setup Instructions

### Step 1: Install Docker

#### macOS

```bash
# Download Docker Desktop from:
# https://www.docker.com/products/docker-desktop/

# Or install via Homebrew
brew install --cask docker

# Start Docker Desktop from Applications
# Verify installation
docker --version
docker-compose --version
```

#### Ubuntu/Linux

```bash
# Remove old versions
sudo apt remove docker docker-engine docker.io containerd runc

# Install prerequisites
sudo apt update
sudo apt install -y ca-certificates curl gnupg lsb-release

# Add Docker GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```

#### Windows (WSL2)

```powershell
# Download Docker Desktop from:
# https://www.docker.com/products/docker-desktop/

# Install and ensure WSL2 backend is enabled
# Verify in PowerShell
docker --version
docker-compose --version
```

---

### Step 2: Clone Repository

```bash
# Navigate to your projects directory
cd ~/Projects  # Or your preferred location

# Clone repository
git clone <repository-url>
cd evidence-analysis-service-p1
```

---

### Step 3: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit environment file
nano .env  # Or use your preferred editor
```

**Required Environment Variables for Docker**:

```env
# Database (Docker uses internal networking)
DATABASE_URL=postgresql://evidence_user:evidence_password@postgres:5432/evidence_analysis

# JWT Authentication
JWT_SECRET_KEY=your-secret-key-here  # Generate with: openssl rand -hex 32
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS (allow frontend)
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# Google Gemini AI
GEMINI_API_KEY_1=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash

# Cloud Storage (GCP or AWS)
CLOUD_STORAGE_PROVIDER=gcp
CLOUD_STORAGE_BUCKETNAME=your-bucket-name
CLOUD_STORAGE_ACCOUNTNAME=your-service-account@project.iam.gserviceaccount.com
CLOUD_STORAGE_SECRET=your-json-key-content

# Celery (Docker uses internal networking)
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
CELERY_WORKER_CONCURRENCY=2

# Email Notifications
IS_NOTIFICATION_ENABLED=true
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=your-mailtrap-user
SMTP_PASSWORD=your-mailtrap-password
SMTP_FROM_EMAIL=noreply@evidence-analysis.com

# Portal URL
PORTAL_BASE_URL=http://localhost:5173
```

**Important**: Docker services use container hostnames (postgres, rabbitmq) instead of localhost.

---

### Step 4: Understand Docker Architecture

The system uses multiple Docker containers:

```
┌──────────────┐
│   frontend   │ (Node.js 20, Vite dev server)
│   :5173      │
└──────────────┘
       ↓
┌──────────────┐
│   backend    │ (Python 3.12, FastAPI)
│   :8000      │
└──────────────┘
       ↓
┌──────────────┬──────────────┬──────────────┐
│  postgres    │  rabbitmq    │    redis     │
│   :5432      │  :5672       │    :6379     │
└──────────────┴──────────────┴──────────────┘
       ↓
┌──────────────┐
│celery-worker │ (Python 3.12, Celery)
└──────────────┘
```

---

### Step 5: Start Services

#### Start All Services (Recommended)

```bash
# Start all services in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend
docker-compose logs -f celery-worker
```

#### Start Specific Services Only

```bash
# Start only backend services (no frontend)
docker-compose up -d postgres rabbitmq redis backend celery-worker

# Start only frontend
docker-compose up -d frontend
```

---

### Step 6: Initialize Database

**First-time setup only:**

```bash
# Wait for PostgreSQL to be ready (check with docker-compose logs postgres)
docker-compose exec backend python db/init_db.py

# Seed default users
docker-compose exec backend python db/seed_data.py

# Run migrations
docker-compose exec backend alembic upgrade head

# Verify database
docker-compose exec postgres psql -U evidence_user -d evidence_analysis -c "\dt"
```

---

### Step 7: Verify Installation

#### Check Service Health

```bash
# Check running containers
docker-compose ps

# All services should be "Up (healthy)"
```

#### Test Backend API

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"1.0.0"}

# Open Swagger UI
open http://localhost:8000/docs  # macOS
xdg-open http://localhost:8000/docs  # Linux
```

#### Test Frontend

```bash
# Open frontend
open http://localhost:5173  # macOS
xdg-open http://localhost:5173  # Linux

# Login with:
# Username: admin
# Password: admin123
```

#### Test RabbitMQ

```bash
# Access management UI
open http://localhost:15672  # macOS
xdg-open http://localhost:15672  # Linux

# Login: guest / guest
# Check Queues tab for "execution_queue"
```

#### Test Database Connection

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U evidence_user -d evidence_analysis

# In psql:
\dt  # List tables
SELECT username FROM users;  # Check users
\q  # Exit
```

---

## Docker Commands Reference

### Service Management

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose stop

# Restart services
docker-compose restart

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes (⚠️ deletes data!)
docker-compose down -v

# View running containers
docker-compose ps

# View all docker containers
docker ps -a
```

### Logs and Debugging

```bash
# View logs for all services
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend
docker-compose logs -f celery-worker
docker-compose logs -f postgres

# View last 100 lines
docker-compose logs --tail=100 backend

# Follow logs in real-time
docker-compose logs -f --tail=50 backend
```

### Execute Commands in Containers

```bash
# Run Python script in backend container
docker-compose exec backend python db/init_db.py

# Open shell in backend container
docker-compose exec backend bash

# Run Alembic migrations
docker-compose exec backend alembic upgrade head

# Connect to PostgreSQL
docker-compose exec postgres psql -U evidence_user -d evidence_analysis

# Check Celery worker status
docker-compose exec celery-worker celery -A celery_worker.celery_app inspect active
```

### Building and Rebuilding

```bash
# Rebuild all images
docker-compose build

# Rebuild specific service
docker-compose build backend

# Rebuild and restart
docker-compose up -d --build

# Pull latest base images and rebuild
docker-compose build --pull
```

### Volume Management

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect evidence-analysis-service-p1_postgres_data

# Remove unused volumes
docker volume prune

# Backup database volume
docker run --rm -v evidence-analysis-service-p1_postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres-backup.tar.gz /data
```

---

## Production Deployment

### Create Production Dockerfile

Create `Dockerfile` in `evidence-analysis-service-p1/`:

```dockerfile
# Backend Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Create Production docker-compose.yml

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: evidence-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: evidence_analysis
      POSTGRES_USER: evidence_user
      POSTGRES_PASSWORD: ${DB_PASSWORD:-evidence_password}
      POSTGRES_INITDB_ARGS: "-E UTF8 --locale=en_US.UTF-8"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U evidence_user -d evidence_analysis"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - evidence-backend-net

  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    container_name: evidence-rabbitmq
    restart: unless-stopped
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-guest}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-guest}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - evidence-backend-net

  redis:
    image: redis:7-alpine
    container_name: evidence-redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    networks:
      - evidence-backend-net

  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: evidence-backend
    restart: unless-stopped
    env_file:
      - .env.production
    environment:
      DATABASE_URL: postgresql://evidence_user:${DB_PASSWORD:-evidence_password}@postgres:5432/evidence_analysis
      CELERY_BROKER_URL: amqp://${RABBITMQ_USER:-guest}:${RABBITMQ_PASSWORD:-guest}@rabbitmq:5672//
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    ports:
      - "${BACKEND_PORT:-8000}:8000"
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    networks:
      - evidence-backend-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: evidence-celery-worker
    restart: unless-stopped
    env_file:
      - .env.production
    environment:
      DATABASE_URL: postgresql://evidence_user:${DB_PASSWORD:-evidence_password}@postgres:5432/evidence_analysis
      CELERY_BROKER_URL: amqp://${RABBITMQ_USER:-guest}:${RABBITMQ_PASSWORD:-guest}@rabbitmq:5672//
    command: celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    networks:
      - evidence-backend-net

  frontend:
    build:
      context: ../evidence-analysis-portal-p1
      dockerfile: Dockerfile
    container_name: evidence-frontend
    restart: unless-stopped
    environment:
      API_ENDPOINT: http://backend:8000
    ports:
      - "${FRONTEND_PORT:-5173}:80"
    depends_on:
      - backend
    networks:
      - evidence-backend-net

volumes:
  postgres_data:
  rabbitmq_data:
  redis_data:

networks:
  evidence-backend-net:
    driver: bridge
```

### Deploy to Production

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Initialize database (first-time only)
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
docker-compose -f docker-compose.prod.yml exec backend python db/seed_data.py

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs for errors
docker-compose logs backend
docker-compose logs postgres

# Check container status
docker-compose ps

# Restart specific service
docker-compose restart backend
```

### Database Connection Failed

```bash
# Check if PostgreSQL is ready
docker-compose exec postgres pg_isready -U evidence_user

# Check database logs
docker-compose logs postgres

# Manually connect to verify
docker-compose exec postgres psql -U evidence_user -d evidence_analysis
```

### Port Already in Use

```bash
# Find process using port
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Change port in docker-compose.yml
ports:
  - "8001:8000"  # Use 8001 instead
```

### Permission Denied Errors

```bash
# Fix volume permissions
docker-compose exec backend chown -R app:app /app/uploads

# Or on host system
sudo chown -R $(whoami):$(whoami) ./uploads
```

### Out of Disk Space

```bash
# Clean up unused images
docker system prune -a

# Remove unused volumes
docker volume prune

# Check disk usage
docker system df
```

### Service Health Check Failing

```bash
# Check service logs
docker-compose logs backend

# Manually test health endpoint
docker-compose exec backend curl http://localhost:8000/health

# Increase health check timeout in docker-compose.yml
healthcheck:
  interval: 30s
  timeout: 10s
  start_period: 60s  # Increase this
```

### Rebuild After Code Changes

```bash
# Rebuild and restart
docker-compose up -d --build

# Or rebuild specific service
docker-compose build backend
docker-compose up -d backend
```

---

## Performance Optimization

### Resource Limits

Add to `docker-compose.yml`:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

### Enable BuildKit

```bash
# Add to ~/.bashrc or ~/.zshrc
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
```

### Multi-stage Builds

Optimize Dockerfile size:

```dockerfile
# Build stage
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Next Steps

- [ ] Review [Environment Setup Guide](environment-setup.md)
- [ ] Set up CI/CD pipeline for automated deployments
- [ ] Configure reverse proxy (Nginx/Traefik)
- [ ] Set up SSL/TLS certificates
- [ ] Implement container orchestration (Kubernetes/Docker Swarm)
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure log aggregation (ELK stack)

---

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Docker Security](https://docs.docker.com/engine/security/)

---

**Need Help?** See the [Troubleshooting Guide](troubleshooting.md) or open an issue in the repository.
