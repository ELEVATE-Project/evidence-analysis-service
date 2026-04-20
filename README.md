# Evidence Analysis Service - Phase 1

FastAPI backend REST API for the Evidence Analysis System.

## Setup

### Prerequisites
- Python 3.12+
- pip
- PostgreSQL 14+

### Installation
1. **Navigate to backend directory**
   ```bash
   cd evidence-analysis-service-p1
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   ```

3. **Activate virtual environment**
   ```bash
   # Linux/macOS
   source venv/bin/activate

   # Windows
   venv\Scripts\activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```

6. **Update required `.env` values**
   - `DATABASE_URL`
   - `JWT_SECRET_KEY`
   - `CORS_ORIGINS`
   - `DEFAULT_TENANT_CODE`
   - `DEFAULT_ORGANIZATION_CODE`
   - `STORAGE_TYPE`
   - `ENTITY_MGMT_BASE_URL`
   - `ENTITY_MGMT_TENANT_ID`
   - `ENTITY_MGMT_ORIGIN`

7. **Initialize database**
   ```bash
   python db/init_db.py
   ```

8. **Seed default users**
   ```bash
   python db/seed_data.py
   ```

9. **Run development server**
   ```bash
   uvicorn main:app --reload
   ```

10. **Run Celery worker (queue processor)**
   ```bash
   celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2
   ```

API: `http://localhost:8000`  
Docs: `http://localhost:8000/docs`
