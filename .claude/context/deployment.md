# Deployment Context

## Docker Compose Stack

```yaml
Services:
  postgres:       PostgreSQL 16-alpine, port 5432
  rabbitmq:       RabbitMQ 3.13-management, ports 5672/15672
  redis:          Redis 7-alpine, port 6379 (optional)
  backend:        Python 3.12-slim, port 8000
  celery-worker:  Python 3.12-slim (same image, different command)
  frontend:       Node 20-alpine, port 5173
```

## Backend Container Command

```bash
pip install --no-cache-dir -r requirements.txt &&
alembic upgrade head &&
python scripts/upload_sample_csvs.py &&
uvicorn main:app --host 0.0.0.0 --port 8000
```

Steps:
1. Install dependencies (dev environments only — production should pre-build image)
2. Apply all pending migrations
3. Seed data + cloud storage bootstrap (upload sample CSVs)
4. Start API server (lifespan re-runs bootstrap — idempotent)

## Celery Worker Command

```bash
pip install --no-cache-dir -r requirements.txt &&
celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2
```

## Environment Variables (required for production)

```bash
# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/evidence_analysis

# Auth
JWT_SECRET_KEY=<64-char random hex: openssl rand -hex 32>
JWT_ALGORITHM=HS256

# Cloud Storage — one of:
CLOUD_STORAGE_PROVIDER=gcp
CLOUD_STORAGE_BUCKETNAME=my-bucket
CLOUD_STORAGE_SECRET=<full service-account JSON>
CLOUD_STORAGE_ACCOUNTNAME=service-account@project.iam.gserviceaccount.com

# OR:
CLOUD_STORAGE_PROVIDER=aws
CLOUD_STORAGE_BUCKETNAME=my-bucket
CLOUD_STORAGE_ACCOUNTNAME=AKIAIOSFODNN7EXAMPLE  # omit for IAM role
CLOUD_STORAGE_SECRET=wJalrXUtnFEMI...           # omit for IAM role
CLOUD_STORAGE_REGION=us-east-1

# AI
GEMINI_API_KEY_1=<api key>
GEMINI_API_KEY_2=<api key>  # optional rotation
GEMINI_API_KEY_3=<api key>  # optional rotation
GEMINI_MODEL=gemini-2.5-flash

# Celery
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
CELERY_RESULT_BACKEND=rpc://

# Entity Management
ENTITY_MGMT_BASE_URL=https://your-entity-service
ENTITY_MGMT_TENANT_ID=your-tenant
ENTITY_MGMT_ORIGIN=https://your-origin

# CORS
CORS_ORIGINS=["https://your-frontend.example.com"]

# SMTP (optional)
IS_NOTIFICATION_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=app-password
SMTP_FROM_EMAIL=no-reply@your-domain.com
PORTAL_BASE_URL=https://your-frontend.example.com
```

## Health Checks

```bash
# API health
GET /health → {"status": "healthy"}

# Migration status
alembic current  # must show b3f8a9c12d45

# Storage bootstrap
psql -c "SELECT sample_input_file_url FROM csv_source_types LIMIT 1;"
# must be non-null

# Celery worker
celery -A celery_worker.celery_app status
```

## Kubernetes / Production Considerations

### Init Container Pattern
```yaml
initContainers:
  - name: migrations
    image: <backend-image>
    command: ["alembic", "upgrade", "head"]
  - name: bootstrap
    image: <backend-image>
    command: ["python", "scripts/upload_sample_csvs.py"]
containers:
  - name: backend
    command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Health Probe
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
```

### Secrets
- `JWT_SECRET_KEY`: Kubernetes Secret or secrets manager
- `CLOUD_STORAGE_SECRET` (SA JSON): Kubernetes Secret with base64 encoding
- Database password: Kubernetes Secret

### Scaling Notes
- API is stateless — scale horizontally
- Celery workers scale independently — `--concurrency` controls per-worker parallelism
- `worker_prefetch_multiplier=1` prevents worker monopolization
- Database pool: `pool_size=10, max_overflow=20` per API replica

## Production Security Checklist

- [ ] Change seed passwords (`admin123`, `user123`) after first deployment
- [ ] `DEBUG=false` in production
- [ ] `CORS_ORIGINS` restricted to actual frontend domain
- [ ] `JWT_SECRET_KEY` is 32+ random bytes, unique per environment
- [ ] Cloud storage bucket is private (signed URLs only)
- [ ] Gemini API keys have usage limits set in GCP console
- [ ] Database has a dedicated user with minimal permissions
- [ ] `EXECUTION_CLEANUP_ON_SUCCESS=true` to avoid workspace disk accumulation
