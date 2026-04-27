# Evidence Analysis Service - Setup Guide

This README contains setup information only.

## Official Dependency Installation Docs

- Python: https://www.python.org/downloads/
- pip: https://pip.pypa.io/en/stable/installation/
- PostgreSQL: https://www.postgresql.org/download/
- RabbitMQ: https://www.rabbitmq.com/download.html
- Redis: https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/
- Celery (installation): https://docs.celeryq.dev/en/stable/getting-started/introduction.html#installation
- Node.js + npm (for frontend): https://nodejs.org/en/download
- Docker Desktop / Docker Engine: https://docs.docker.com/get-docker/
- Docker Compose: https://docs.docker.com/compose/install/

## Local Setup (Backend)

1. Navigate to backend directory:

```bash
cd evidence-analysis-service-p1
```

2. Create and activate virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment:

```bash
cp .env.example .env
```

5. Update required `.env` values:

- Check all the env keys in .env.sample and add values in .env

6. Initialize database:

```bash
python db/init_db.py
python db/seed_data.py
```

7. Run database migrations:

```bash
alembic upgrade head
```

8. Upload sample CSV files to cloud storage:

```bash
# Upload sample files and update database with cloud paths
python scripts/upload_sample_csvs.py
```

**Note:** The upload script should be run after the migration. It uploads sample CSV files from `public/sample-csv/projects/` to cloud storage and updates the database with the file paths.

9. Start API server:

```bash
uvicorn main:app --reload
```

10. Start Celery worker (separate terminal):

```bash
celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2
```

Backend URL: `http://localhost:8000`  
Swagger Docs: `http://localhost:8000/docs`

## Local Setup (Frontend)

1. Open a new terminal and navigate:

```bash
cd evidence-analysis-portal-p1
```

2. Install dependencies and run:

```bash
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`

## Docker Compose Setup (Frontend + Backend on Same Network)

From project root (`Phase1`):

```bash
docker compose up -d
```

Services:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- PostgreSQL: `localhost:5432`
- RabbitMQ: `localhost:5672` (Management UI: `http://localhost:15672`)
- Redis: `localhost:6379`

## Migrations & Scripts

### Database Migrations (Alembic)

**Run migrations:**
```bash
alembic upgrade head
```

**Check current version:**
```bash
alembic current
```

**View migration history:**
```bash
alembic history --verbose
```

**Rollback one migration:**
```bash
alembic downgrade -1
```

**Create new migration:**
```bash
alembic revision -m "description"
```

**Auto-generate migration from model changes:**
```bash
alembic revision --autogenerate -m "description"
```

### Setup Order

**New Installation:**
```bash
python db/init_db.py
python db/seed_data.py
alembic upgrade head
python scripts/upload_sample_csvs.py
```

**Existing Installation:**
```bash
alembic upgrade head
python scripts/upload_sample_csvs.py
```
