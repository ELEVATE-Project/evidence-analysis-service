# Command: Validate Deployment

**Usage:** `/validate-deployment`

Validate that the application is correctly deployed and all subsystems are healthy.

## Pre-Deployment Checklist

```bash
# 1. Migrations at head
alembic current
# Expected: b3f8a9c12d45 (head)

# 2. Sample CSV bootstrap completed
psql $DATABASE_URL -c "
  SELECT type_key, sample_input_file_url, sample_criteria_file_url
  FROM csv_source_types WHERE type_key = 'project_report';
"
# Expected: both URLs set to "/projects/sample_input.csv" etc.

# 3. Health check
curl -s http://localhost:6002/health | python -m json.tool
# Expected: {"status": "healthy"}

# 4. API responds
curl -X POST http://localhost:6002/api/v1/auth/login \
  -d "username=admin&password=admin123" | python -m json.tool
# Expected: {"access_token": "...", "token_type": "bearer"}

# 5. Celery worker connected
celery -A celery_worker.celery_app status
# Expected: celery@<hostname>: OK

# 6. RabbitMQ queue exists
rabbitmqctl list_queues name messages
# Expected: execution_queue  0
```

## Post-Deployment Smoke Test

```bash
TOKEN=$(curl -s -X POST http://localhost:6002/api/v1/auth/login \
  -d "username=admin&password=admin123" | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

# Test config endpoint
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:6002/api/v1/config/list?type=project" | python -m json.tool
# Expected: {"success": true, "data": [...]}

# Test entities (external service)
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:6002/api/v1/states" | python -m json.tool
# Expected: {"success": true, "data": [...]} or upstream error with success=false

# Test sample file download URL generation
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:6002/api/v1/config/1/sample/input" | python -m json.tool
# Expected: {"download_url": "https://...", "expires_in_seconds": 600}
```

## Docker Deployment Validation

```bash
# All containers running
docker-compose ps
# Expected: all containers "Up"

# Check backend startup logs
docker-compose logs backend | tail -50
# Must see:
#   "Database migrations are current"
#   "=== Storage Bootstrap: starting ==="
#   "deep storage validation passed"
#   "=== Storage Bootstrap: complete ==="
#   "Default seed data applied"
#   "Background worker initialized"

# Check no errors on startup
docker-compose logs backend | grep -E "ERROR|CRITICAL|Exception"

# Celery worker connected
docker-compose logs celery-worker | grep "ready"
```

## Failure Diagnosis Matrix

| Failure | Check | Fix |
|---------|-------|-----|
| Migration out of date | `alembic current` | `alembic upgrade head` |
| sample_input_file_url null | Bootstrap logs | `python scripts/upload_sample_csvs.py` |
| StorageService init fails | `CLOUD_STORAGE_PROVIDER` | Check provider + credentials |
| Bucket validation fails | Deep validation error message | Check IAM permissions |
| Celery not connecting | RabbitMQ status | Verify `CELERY_BROKER_URL` |
| 401 on login | JWT_SECRET_KEY | Check env matches between restarts |
| Entity service errors | `ENTITY_MGMT_BASE_URL` | Expected if external service unavailable |
