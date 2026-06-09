# Environment Setup Guide - Evidence Analysis System

Complete reference for all environment variables used in the Evidence Analysis System.

---

## Table of Contents

- [Backend Environment Variables](#backend-environment-variables)
- [Frontend Environment Variables](#frontend-environment-variables)
- [Generating Secure Keys](#generating-secure-keys)
- [Environment-Specific Configurations](#environment-specific-configurations)
- [External Service Configuration](#external-service-configuration)

---

## Backend Environment Variables

Create a `.env` file in `evidence-analysis-service-p1/` directory.

### Application Settings

```env
# Application Name and Version
APP_NAME=Evidence Analysis System
APP_VERSION=1.0.0

# Debug Mode (set to False in production)
DEBUG=False
```

---

### Database Configuration

```env
# PostgreSQL Connection String
# Format: postgresql://username:password@host:port/database_name
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/evidence_analysis

# For Docker:
# DATABASE_URL=postgresql://evidence_user:evidence_password@postgres:5432/evidence_analysis
```

**Required**: Yes  
**Example**: `postgresql://myuser:mypassword@localhost:5432/mydb`

---

### JWT Authentication

```env
# Secret key for JWT token signing (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your-secret-key-here

# Algorithm for JWT token encoding
JWT_ALGORITHM=HS256

# Token expiration time in minutes (1440 = 24 hours)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

**Required**: Yes  
**Security**: Use a strong, randomly generated key. Never commit to version control.

**Generate JWT Secret**:
```bash
openssl rand -hex 32
# Or
python -c "import secrets; print(secrets.token_hex(32))"
```

---

### CORS Configuration

```env
# JSON array of allowed origins
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# For production:
# CORS_ORIGINS=["https://yourdomain.com","https://app.yourdomain.com"]
```

**Required**: Yes  
**Format**: JSON array as string

---

### Execution Defaults

```env
# Default tenant code for multi-tenant setup
DEFAULT_TENANT_CODE=default

# Default organization code
DEFAULT_ORGANIZATION_CODE=default_code
```

**Required**: Yes  
**Note**: Used for multi-tenant isolation

---

### Entity Management Service

```env
# Base URL for external entity management API
ENTITY_MGMT_BASE_URL=https://dev.elevate-apis.shikshalokam.org

# Mandatory upstream headers
ENTITY_MGMT_TENANT_ID=shikshalokam
ENTITY_MGMT_ORIGIN=https://dev.elevate-sandbox.shikshalokam.org

# Reliability settings
ENTITY_MGMT_TIMEOUT_SECONDS=10
ENTITY_MGMT_RETRY_ATTEMPTS=2
ENTITY_MGMT_RETRY_BACKOFF_SECONDS=0.5

# Optional in-memory cache for /states endpoint
ENTITY_MGMT_CACHE_ENABLED=true
ENTITY_MGMT_STATES_CACHE_TTL_SECONDS=900
```

**Required**: No (if not using external entity service)  
**Purpose**: Fetch states, districts, and geographical data

---

### Cloud Storage Configuration

#### Google Cloud Platform (GCP)

```env
# Storage provider
CLOUD_STORAGE_PROVIDER=gcp
CLOUD_STORAGE=GCP

# GCP Configuration
CLOUD_STORAGE_REGION=your-gcp-project
CLOUD_ENDPOINT=

# Service Account Details
CLOUD_STORAGE_ACCOUNTNAME=service-account@project.iam.gserviceaccount.com
CLOUD_STORAGE_BUCKETNAME=your-bucket-name
CLOUD_STORAGE_BUCKET_TYPE=private

# Service Account JSON Key (paste full key content)
CLOUD_STORAGE_SECRET=-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----\n
```

#### Amazon Web Services (AWS S3)

```env
# Storage provider
CLOUD_STORAGE_PROVIDER=aws
CLOUD_STORAGE=AWS

# AWS Configuration
CLOUD_STORAGE_REGION=us-east-1
CLOUD_ENDPOINT=https://s3.amazonaws.com

# AWS Credentials
CLOUD_STORAGE_ACCOUNTNAME=your-access-key-id
CLOUD_STORAGE_SECRET=your-secret-access-key
CLOUD_STORAGE_BUCKETNAME=your-bucket-name
CLOUD_STORAGE_BUCKET_TYPE=private
```

#### Local Storage (Fallback)

```env
# Local filesystem storage
LOCAL_STORAGE_PATH=./uploads
```

**Required**: Yes (choose one provider)  
**Security**: Never commit cloud credentials to version control

---

### AI Model Configuration (Google Gemini)

```env
# Google Gemini API Keys (supports rotation)
GEMINI_API_KEY_1=AIzaSy...your-api-key
GEMINI_API_KEY_2=AIzaSy...your-second-key (optional)
GEMINI_API_KEY_3=AIzaSy...your-third-key (optional)

# Model version
GEMINI_MODEL=gemini-2.5-flash
```

**Required**: Yes (at least GEMINI_API_KEY_1)  
**Get API Key**: [Google AI Studio](https://ai.google.dev/)

**Supported Models**:
- `gemini-2.5-flash` (recommended, fastest)
- `gemini-1.5-pro` (more accurate, slower)
- `gemini-1.5-flash` (balanced)

---

### Email Notification Configuration

```env
# Enable/disable notifications
IS_NOTIFICATION_ENABLED=true

# SMTP Server Settings
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_TIMEOUT_SECONDS=30

# SMTP Authentication
SMTP_USER=your-smtp-username
SMTP_PASSWORD=your-smtp-password
SMTP_API_KEY=  # Alternative to user/password

# Email Sender Configuration
SMTP_FROM_EMAIL=noreply@evidence-analysis.com
SMTP_FROM_NAME=Evidence Analysis System

# Retry Settings
SMTP_MAX_RETRIES=3
SMTP_RETRY_BACKOFF_SECONDS=1

# Portal URL for email links
PORTAL_BASE_URL=http://localhost:5173
```

**Required**: No (notifications optional)

**SMTP Providers**:
- **Mailtrap** (testing): sandbox.smtp.mailtrap.io:587
- **SendGrid**: smtp.sendgrid.net:587
- **Amazon SES**: email-smtp.us-east-1.amazonaws.com:587
- **Gmail**: smtp.gmail.com:587 (requires app password)

---

### Background Processing & Execution

```env
# Thread Pool Settings (fallback)
MAX_CONCURRENT_JOBS=5
WORKER_CHECK_INTERVAL=5

# Celery + RabbitMQ Configuration
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
CELERY_RESULT_BACKEND=rpc://
CELERY_TASK_QUEUE=execution_queue
CELERY_TASK_ROUTING_KEY=execution.process
CELERY_MAX_RETRIES=3
CELERY_RETRY_BACKOFF_SECONDS=30
CELERY_WORKER_CONCURRENCY=2

# Execution Workspace Settings
EXECUTION_WORKSPACE_ROOT=/tmp/evidence_analysis/executions
EXECUTION_CLEANUP_ON_SUCCESS=true

# Processing Scripts
PREPROCESS_SCRIPT_PATH=scripts/pre-processor/1-pre-processor.py
PROCESSOR_SCRIPT_PATH=scripts/processor/1-main-parallel-script.py
PROCESSOR_MAX_ROWS=0  # 0 = unlimited
PROCESSOR_RESUME_FROM_CHECKPOINT=false

# Execution Cost & Time Estimates
ESTIMATED_COST_PER_INPUT_ROW=0.001
ESTIMATED_TIME_SECONDS_PER_INPUT_ROW=0.5
```

**Required**: Yes (for background task processing)  
**Note**: For Docker, use container hostnames (rabbitmq instead of localhost)

---

### File Splitting Configuration

```env
# Manual Mode (explicit control)
# SPLIT_FILES=yes
# ROWS_PER_FILE=5000

# Dynamic Mode (automatic optimization)
ENABLE_DYNAMIC_SPLITTING=true
MAX_SPLIT_FILES=100
MIN_ROWS_FOR_SPLITTING=1000
TARGET_ROWS_PER_SPLIT_MIN=500
TARGET_ROWS_PER_SPLIT_MAX=2000
OPTIMAL_ROWS_PER_SPLIT=1000
```

**Required**: No (uses dynamic defaults)

---

### File Upload & Validation

```env
# Upload Limits
MAX_UPLOAD_SIZE=104857600  # 100 MB in bytes
ALLOWED_EXTENSIONS=[".csv"]

# Signed URL Expiry
SIGNED_UPLOAD_URL_EXPIRY_SECONDS=900    # 15 minutes
SIGNED_DOWNLOAD_URL_EXPIRY_SECONDS=600  # 10 minutes

# Interactive Criteria Validation
CRITERIA_VALIDATE_MAX_ITEMS=25
```

**Required**: No (uses defaults)

---

## Frontend Environment Variables

Create a `.env` file in `evidence-analysis-portal-p1/` directory.

```env
# =============================
# Vite Dev Server Configuration
# =============================
APPLICATION_PORT=5173
APPLICATION_BASE_URL=/api/v1
API_ENDPOINT=http://localhost:8000

# =============================
# Build Configuration
# =============================
APPLICATION_BUILD_OUT_DIR=dist
APPLICATION_BUILD_SOURCEMAP=false

# =============================
# Auth Session Configuration
# =============================
APPLICATION_AUTH_REFRESH_BUFFER_MS=300000  # 5 minutes
APPLICATION_AUTH_FALLBACK_EXPIRY_HOURS=24  # 24 hours

# =============================
# Browser Storage Keys
# =============================
APPLICATION_AUTH_TOKEN_STORAGE_KEY=token
APPLICATION_AUTH_USER_STORAGE_KEY=user
APPLICATION_AUTH_EXPIRES_AT_STORAGE_KEY=token_expires_at
APPLICATION_AUTH_REMEMBER_ME_STORAGE_KEY=remember_me

# =============================
# Defaults
# =============================
APPLICATION_DEFAULT_CSV_TYPE_ID=project_report
APPLICATION_VALIDATE_CRITERIA_MAX_ITEMS=25
```

**Required**: Yes  
**Note**: Vite uses `import.meta.env.VITE_*` for exposing variables to client code

---

## Generating Secure Keys

### JWT Secret Key

```bash
# Method 1: OpenSSL
openssl rand -hex 32

# Method 2: Python
python -c "import secrets; print(secrets.token_hex(32))"

# Method 3: Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

### Service Account JSON (GCP)

1. Go to [GCP Console](https://console.cloud.google.com/)
2. Navigate to IAM & Admin → Service Accounts
3. Create or select service account
4. Add Keys → Create New Key → JSON
5. Download JSON file
6. Copy entire content to `CLOUD_STORAGE_SECRET` (escape newlines with \n)

```bash
# Convert JSON to single-line string
cat service-account.json | jq -c | sed 's/"/\\"/g'
```

---

## Environment-Specific Configurations

### Development (.env)

```env
DEBUG=True
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/evidence_analysis
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
PORTAL_BASE_URL=http://localhost:5173
```

### Staging (.env.staging)

```env
DEBUG=False
CORS_ORIGINS=["https://staging.yourdomain.com"]
DATABASE_URL=postgresql://user:pass@staging-db.internal:5432/evidence_db
CELERY_BROKER_URL=amqp://user:pass@staging-rabbitmq.internal:5672/staging
PORTAL_BASE_URL=https://staging.yourdomain.com
```

### Production (.env.production)

```env
DEBUG=False
CORS_ORIGINS=["https://yourdomain.com"]
DATABASE_URL=postgresql://user:strong-pass@prod-db.internal:5432/evidence_db
CELERY_BROKER_URL=amqp://user:strong-pass@prod-rabbitmq.internal:5672/prod
PORTAL_BASE_URL=https://yourdomain.com
IS_NOTIFICATION_ENABLED=true
EXECUTION_CLEANUP_ON_SUCCESS=true
```

---

## External Service Configuration

### Mailtrap (Email Testing)

```env
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=your-mailtrap-inbox-username
SMTP_PASSWORD=your-mailtrap-inbox-password
SMTP_USE_TLS=true
```

Sign up: [mailtrap.io](https://mailtrap.io/)

### SendGrid (Production Email)

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.your-sendgrid-api-key
SMTP_USE_TLS=true
```

Sign up: [sendgrid.com](https://sendgrid.com/)

### Google Cloud Storage (GCP)

1. Create GCP project
2. Enable Cloud Storage API
3. Create storage bucket
4. Create service account with "Storage Object Admin" role
5. Download service account JSON key
6. Copy key content to `CLOUD_STORAGE_SECRET`

### AWS S3

1. Create AWS account
2. Create S3 bucket
3. Create IAM user with S3 access policy
4. Generate access key and secret
5. Add to environment variables

---

## Environment Validation

### Check Required Variables

```bash
# Backend
cd evidence-analysis-service-p1
source venv/bin/activate
python -c "from core.config import Settings; s = Settings(); print('✅ Configuration valid')"

# Frontend
cd evidence-analysis-portal-p1
npm run dev  # Will show missing variables
```

### Test Database Connection

```bash
python -c "from db.database import engine; print(engine.connect())"
```

### Test Cloud Storage

```bash
python -c "from services.storage_service import StorageService; print(StorageService().test_connection())"
```

### Test SMTP

```bash
python -c "from services.email_service import EmailService; EmailService().send_test_email('your@email.com')"
```

---

## Security Best Practices

1. **Never commit `.env` files** to version control
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   echo ".env.*" >> .gitignore
   ```

2. **Use strong passwords** (minimum 16 characters, mixed case, numbers, symbols)

3. **Rotate API keys** regularly (quarterly recommended)

4. **Restrict CORS origins** to specific domains (not *)

5. **Use HTTPS** in production for all external services

6. **Encrypt sensitive data** at rest and in transit

7. **Use environment-specific credentials** (dev/staging/prod)

8. **Limit service account permissions** to minimum required

9. **Enable audit logging** for sensitive operations

10. **Use secrets management** tools (AWS Secrets Manager, HashiCorp Vault)

---

## Troubleshooting

### "Configuration Error" on Startup

```bash
# Check for syntax errors in .env
cat .env | grep -v "^#" | grep "="

# Verify no trailing spaces
cat .env | sed 's/ *$//' > .env.tmp && mv .env.tmp .env
```

### "Invalid JWT Secret"

```bash
# Generate new secret
openssl rand -hex 32

# Update .env
JWT_SECRET_KEY=<new-secret>
```

### "Cloud Storage Connection Failed"

```bash
# Verify credentials
gcloud auth application-default print-access-token  # GCP
aws s3 ls  # AWS

# Test connection
python -c "from services.storage_service import StorageService; print(StorageService().test_connection())"
```

### "SMTP Authentication Failed"

```bash
# Test SMTP connection
python -c "import smtplib; smtplib.SMTP('sandbox.smtp.mailtrap.io', 587).starttls(); print('✅ SMTP OK')"
```

---

## Quick Reference

### Minimal Required Variables

```env
# Backend
DATABASE_URL=postgresql://user:pass@host:5432/db
JWT_SECRET_KEY=your-secret-key
GEMINI_API_KEY_1=your-gemini-key
CLOUD_STORAGE_PROVIDER=gcp
CLOUD_STORAGE_BUCKETNAME=your-bucket
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//

# Frontend
APPLICATION_PORT=5173
API_ENDPOINT=http://localhost:8000
```

---

**Need Help?** See the [Troubleshooting Guide](troubleshooting.md) or open an issue in the repository.
