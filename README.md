# Evidence Analysis Service - Phase 1

FastAPI backend REST API for the Evidence Analysis System.

## Setup

### Prerequisites
- Python 3.12+
- pip (Python package manager)
- PostgreSQL 14+ (for production databases)

### Installation

1. **Navigate to backend directory**:
   ```bash
   cd evidence-analysis-service-p1
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate virtual environment**:
   ```bash
   # On Linux/macOS
   source venv/bin/activate
   
   # On Windows
   venv\Scripts\activate
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables**:
   ```bash
   cp .env.example .env  # If you have a template, otherwise create .env
   ```
   
   Edit `.env` and set these required variables:
   - `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:password@localhost:5432/evidence_db`)
   - `JWT_SECRET_KEY`: Secret key for JWT tokens
   - `JWT_ALGORITHM`: Algorithm for JWT (default: HS256)
   - `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time in minutes (default: 1440 for 24 hours)
   - `STORAGE_TYPE`: Storage provider ("gcp", "s3", or "local")
   - `GCP_PROJECT_ID`, `GCP_BUCKET_NAME`, `GOOGLE_APPLICATION_CREDENTIALS`: For GCP storage
   - `GEMINI_API_KEY`: API key for Google Gemini AI
   - `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`: For email notifications

6. **Initialize database**:
   ```bash
   # Create database tables
   python db/init_db.py
   ```
   
   This creates the required tables: `users` and `executions`

## Seeding Default Data

### Default Users

The system includes three hardcoded users for Phase 1. These users are automatically created on first login attempt:

| Username | Password | Role | Email |
|----------|----------|------|-------|
| `admin` | `admin123` | System Administrator | admin@shishalokam.com |
| `program_designer` | `user123` | Program Designer | program_designer@shishalokam.com |
| `analyst` | `user123` | Analyst | analyst@shishalokam.com |

All users belong to:
- **Tenant**: `default`
- **Organization**: `default_code`

### First Login

Users are created automatically on their first login attempt. Simply:

1. Start the development server:
   ```bash
   uvicorn main:app --reload
   ```

2. Navigate to the frontend at `http://localhost:5173`

3. Login with one of the default credentials above

4. On first login, the user account is automatically created in the database

## Running Development Server

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

Access API documentation at `http://localhost:8000/docs`
