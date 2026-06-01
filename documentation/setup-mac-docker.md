# macOS — Docker Setup Guide

Setup using Docker on **macOS Monterey 12.0+, Ventura 13.0+, or Sonoma 14.0+**.

All services (PostgreSQL, RabbitMQ, backend, Celery worker, frontend) run as containers. No local installation of Python, Node, or databases required.

> Looking for native setup instead? See [setup-mac-native.md](setup-mac-native.md).

---

## Before You Start

> **Always run `cp .env.example .env` and edit the copy.**
> Docker uses container service names as hostnames (`postgres`, `rabbitmq`), **not** `localhost`. This is the most common Docker setup mistake.

---

## Step 1: Install Docker Desktop

```bash
brew install --cask docker
```

Open **Docker Desktop** from Applications and wait until the whale icon in the menu bar is steady (not animating).

```bash
docker --version
docker compose version
```

---

## Step 2: Clone Repository

```bash
mkdir -p ~/Projects && cd ~/Projects
git clone <repository-url>
cd evidence-analysis-service-p1
```

---

## Step 3: Configure Environment

```bash
cp .env.example .env
nano .env
```

Required values — note the container hostnames (`postgres`, `rabbitmq`):

```env
DATABASE_URL=postgresql://evidence_user:evidence_password@postgres:5432/evidence_analysis
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
JWT_SECRET_KEY=<generate with: openssl rand -hex 32>
CORS_ORIGINS=["http://localhost:5173"]
GEMINI_API_KEY_1=<your-gemini-key>
CLOUD_STORAGE_PROVIDER=gcp
CLOUD_STORAGE_BUCKETNAME=<your-bucket>
CLOUD_STORAGE_ACCOUNTNAME=<service-account-email>
CLOUD_STORAGE_SECRET=<service-account-json-or-key>
IS_NOTIFICATION_ENABLED=true
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=<mailtrap-user>
SMTP_PASSWORD=<mailtrap-password>
```

---

## Step 4: Start All Services

```bash
docker compose up -d
```

This starts services in dependency order: PostgreSQL → RabbitMQ → backend (runs `alembic upgrade head` automatically) → Celery worker → frontend.

```bash
# Follow all logs
docker compose logs -f

# Follow a specific service
docker compose logs -f backend
docker compose logs -f celery-worker
```

---

## Step 5: Verify

```bash
# All containers should show "Up (healthy)"
docker compose ps

# Backend API
curl http://localhost:6002/health
# Expected: {"status":"healthy","version":"1.0.0"}

# Database tables
docker compose exec postgres psql -U evidence_user -d evidence_analysis -c "\dt"
```

Open http://localhost:5173 and login with `admin` / `admin123`.

**Access points:**

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:6002/docs |
| RabbitMQ UI | http://localhost:15672 (guest/guest) |

---

## Common Commands

```bash
# Stop (keeps data volumes)
docker compose stop

# Stop and remove containers (keeps data volumes)
docker compose down

# Stop and remove everything including data ⚠️
docker compose down -v

# Restart a single service
docker compose restart backend

# Rebuild after code changes
docker compose up -d --build

# Open a shell inside a container
docker compose exec backend bash

# Run migrations manually
docker compose exec backend alembic upgrade head
```

---

## Troubleshooting

### Container fails to start
```bash
docker compose logs backend
docker compose logs postgres
docker compose ps
```

### `Connection refused` or `could not connect to server`
In Docker, services communicate using their service names, not `localhost`. Verify your `.env`:
```env
DATABASE_URL=postgresql://evidence_user:evidence_password@postgres:5432/evidence_analysis
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
```

### Port already in use
If port 5432 or 5672 is used by a locally running service:
```bash
# Stop native services
brew services stop postgresql@16 rabbitmq

# Or change the host port in docker-compose.yml
ports:
  - "8001:8000"
```

### Users / seed data missing (login fails)

Default users (`admin`, `program_designer`, `analyst`) and the CSV source type are seeded automatically when the backend container starts. If login fails or the `users` table is empty, the backend likely failed to start cleanly (often due to missing cloud storage credentials).

**Step 1: Check why the backend failed**
```bash
docker compose logs backend
```

**Step 2: Fix any startup error** (usually a missing env var — see [Configure Environment](#step-3-configure-environment))

**Step 3: Re-seed manually once the container is running**
```bash
docker compose exec backend python db/seed_data.py
```

This is idempotent — safe to run even if some seed records already exist.

### Rebuild after dependency changes
```bash
docker compose build --no-cache backend
docker compose up -d backend celery-worker
```

### Out of disk space
```bash
docker system prune -a    # removes unused images
docker volume prune        # removes unused volumes (keeps named volumes with data)
docker system df           # check usage
```

---

## Uninstall

```bash
# Remove containers and data volumes for this project
docker compose down -v

# Remove built images
docker compose down --rmi all

# Uninstall Docker Desktop
brew uninstall --cask docker
rm -rf ~/Library/Group\ Containers/group.com.docker
```
