<div align="center">

# Evidence Analysis System

Evidence analysis platform with FastAPI backend, React frontend, AI-powered processing via Google Gemini, and distributed task execution with Celery.

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
[![Python](https://img.shields.io/badge/python-3.12+-brightgreen.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2.0-61DAFB.svg)](https://react.dev/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)

</div>

## </br>

## 💻 Supported Operating Systems

- **Ubuntu** (Recommended: Version 20.04 and above)
- **Windows** (Recommended: Version 11 and above, via WSL2)
- **macOS** (Recommended: Version 12 Monterey and above)

---

<br>

## ✨ About

The **Evidence Analysis System** is an intelligent platform designed to process and analyze CSV-based evidence data using AI-powered natural language processing. The system automates the evaluation of evidence against predefined criteria using Google Gemini AI, generating comprehensive analytical reports with scoring and recommendations. It streamlines evidence review workflows by combining automated analysis with distributed background processing, making it ideal for educational assessments, program evaluations, and data-driven decision making.

### Key Features

- 🤖 **AI-Powered Analysis** via Google Gemini (gemini-2.5-flash)
- 🔄 **Distributed Processing** with Celery + RabbitMQ
- ☁️ **Multi-Cloud Storage** (GCP, AWS S3, Local)
- 🚀 **RESTful API** with FastAPI and auto-generated docs
- 💻 **Modern Frontend** with React 18 + Tailwind CSS
- 🔐 **JWT Authentication** with bcrypt password hashing
- 📧 **Email Notifications** for execution completion

---

<br>

## 🏗️ Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  React Frontend │─────▶│  FastAPI Backend │─────▶│   PostgreSQL    │
│   (Port 5173)   │◀─────│   (Port 8000)    │◀─────│   (Port 5432)   │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
              ┌──────────┐  ┌──────────┐  ┌──────────┐
              │ RabbitMQ │  │  Celery  │  │ Cloud    │
              │          │  │  Worker  │  │ Storage  │
              └──────────┘  └──────────┘  └──────────┘
```

---

## Tech Stack

**Backend**: FastAPI, PostgreSQL, Celery, RabbitMQ, SQLAlchemy, Google Gemini AI  
**Frontend**: React 18, Vite, Tailwind CSS, shadcn/ui, Axios, Chart.js  
**Infrastructure**: Docker, Docker Compose, Alembic, Redis (optional)

<details>
<summary>View detailed tech stack</summary>

### Backend
- FastAPI 0.104.1 (Python 3.12), PostgreSQL 14+, SQLAlchemy 2.0.23
- Celery 5.4.0, RabbitMQ 3.13, Redis 7 (optional)
- JWT Auth (python-jose), bcrypt 4.1.1
- Cloud Storage: GCP (google-cloud-storage 2.14.0), AWS (boto3 1.29.7)
- AI: google-generativeai 0.3.1 (Gemini 2.5 Flash)
- Email: aiosmtplib 3.0.1
- Data: pandas 2.1.3, numpy 1.26.2

### Frontend
- React 18.2.0, Vite 5.0.8, React Router 6.20.0
- Tailwind CSS 3.4.1, shadcn/ui, Material-UI 5.14.20
- Axios 1.6.2, Chart.js 4.4.0, react-chartjs-2 5.2.0
- PDF: html2canvas 1.4.1, jspdf 2.5.1
</details>

## ✨ Setup & Deployment Guide

This section outlines the different ways to set up the **Evidence Analysis System**. Please select the deployment environment and setup method that best suits your needs.

---

<details>
<summary> 🚀 <b>Evidence Analysis Application</b></summary>
<br>

This setup is ideal for **local development and testing**, where only the core Evidence Analysis Service components are required.

#### I. Docker Setup (Recommended)

-   [Setup guide for Ubuntu](documentation/setup-docker.md#ubuntu)
-   [Setup guide for macOS](documentation/setup-docker.md#macos)
-   [Setup guide for Windows](documentation/setup-docker.md#windows)

<br>

#### II. Native Setup (PM2 Managed Services)

-   [Setup guide for Ubuntu](documentation/setup-ubuntu.md)
-   [Setup guide for macOS](documentation/setup-mac.md)
-   [Setup guide for Windows](documentation/setup-docker.md#windows-wsl2)

</details>

---

<br>

## 📖 Related Documentation & Tools

### 🗂️ System Architecture Diagrams

Explore the system architecture for the Evidence Analysis platform below.  
Click to expand and view the diagram.

<br>

<details>
<summary>📂 <b>Evidence Analysis System Architecture</b></summary>
<br>
<pre>
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  React Frontend │─────▶│  FastAPI Backend │─────▶│   PostgreSQL    │
│   (Port 5173)   │◀─────│   (Port 8000)    │◀─────│   (Port 5432)   │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
              ┌──────────┐  ┌──────────┐  ┌──────────┐
              │ RabbitMQ │  │  Celery  │  │ Cloud    │
              │          │  │  Worker  │  │ Storage  │
              └──────────┘  └──────────┘  └──────────┘
</pre>
</details>

> **Tip:** For more architectural details, refer to the setup guides in the documentation folder.

---

### 🧪 API Documentation & Postman Collections

-   **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs) - Interactive API documentation
-   **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc) - Alternative API documentation
-   **OpenAPI Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json) - OpenAPI specification

<details>
<summary>View Key API Endpoints</summary>

**Authentication**
- `POST /api/v1/auth/login` - Authenticate user
- `POST /api/v1/auth/logout` - Logout user
- `GET /api/v1/auth/me` - Get current user

**Executions**
- `GET /api/v1/executions` - List all executions
- `POST /api/v1/executions` - Create new execution
- `GET /api/v1/executions/{id}` - Get execution details
- `POST /api/v1/executions/{id}/run` - Start processing
- `PATCH /api/v1/executions/{id}` - Update execution
- `DELETE /api/v1/executions/{id}` - Delete execution

**Reports**
- `GET /api/v1/reports` - List all reports
- `GET /api/v1/reports/{id}` - Get report details
- `GET /api/v1/reports/{id}/download` - Download report

**Cloud Services**
- `POST /api/v1/cloud/signed-upload-url` - Get signed upload URL
- `POST /api/v1/cloud/signed-download-url` - Get signed download URL

**Example API Call**:
```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Get executions with token
curl -X GET http://localhost:8000/api/v1/executions \
  -H "Authorization: Bearer <your-access-token>"
```
</details>

---

### 🔖 Versioning & Documentation Links

This README is focused on the **1.0.0 Setup Guide** for the Evidence Analysis System.

-   **Current Version (1.0.0) Documentation**  
    All setup links above point to the **1.0.0** guides.

-   **Detailed Documentation**
    -   [Environment Setup Guide](documentation/environment-setup.md) - Complete environment variable reference
    -   [Troubleshooting Guide](documentation/troubleshooting.md) - Common issues and solutions
    -   [Documentation Hub](documentation/README.md) - Complete documentation index

---

### 📦 Service Ports & Access

| Service | Port | Access URL | Credentials |
|---------|------|------------|-------------|
| Frontend Portal | 5173 | http://localhost:5173 | admin / admin123 |
| Backend API | 8000 | http://localhost:8000 | - |
| API Documentation | 8000 | http://localhost:8000/docs | - |
| PostgreSQL | 5432 | localhost:5432 | postgres / postgres |
| RabbitMQ | 5672 | AMQP connection | guest / guest |
| RabbitMQ Management | 15672 | http://localhost:15672 | guest / guest |
| Redis (Optional) | 6379 | localhost:6379 | - |

**Default Application Users** (⚠️ change in production):
- **admin** / admin123 (Administrator)
- **program_designer** / user123 (Program Designer)
- **analyst** / user123 (Analyst)

---

### 🛠️ Helper Scripts & Tools

The system includes several helper scripts to automate common tasks:

```bash
cd documentation/scripts

./setup.sh        # Automated setup and installation
./start.sh        # Start all services
./stop.sh         # Stop all services gracefully
./reset-db.sh     # Reset database (⚠️ deletes all data)
./health-check.sh # System health check and diagnostics
```

---

### 🔍 Quick Verification

After installation, verify your setup:

```bash
# Check backend health
curl http://localhost:8000/health

# Check database connection
psql -U postgres -d evidence_analysis -c "\dt"

# Check RabbitMQ
curl http://localhost:15672/api/overview -u guest:guest

# Or use the health check script
cd documentation/scripts && ./health-check.sh
```

**Login to Portal**:
1. Open [http://localhost:5173](http://localhost:5173)
2. Login with: `admin` / `admin123`
3. Navigate to "New Execution" to test functionality

---

<br>

## 🏗️ Project Structure

<details>
<summary>View Project Structure</summary>

```
evidence-analysis-service-p1/
├── core/                      # Core configuration & dependency injection
│   ├── config.py               # Application configuration
│   └── dependencies.py         # Dependency injection setup
├── db/                        # Database layer
│   ├── database.py            # Database connection & session
│   ├── init_db.py             # Database initialization
│   ├── seed_data.py           # Default user seeding
│   ├── schema.sql             # SQL schema
│   └── migrations/            # Alembic migrations
├── models/                    # Data models
│   ├── execution.py           # Execution model
│   ├── user.py                # User model
│   ├── csv_source_type.py     # CSV source type model
│   └── schemas.py             # Pydantic request/response schemas
├── routers/                   # API endpoints
│   ├── auth.py                # Authentication endpoints
│   ├── executions.py          # Execution CRUD endpoints
│   ├── reports.py             # Report endpoints
│   ├── cloud_services.py      # Cloud storage endpoints
│   └── entities.py            # Entity management endpoints
├── services/                  # Business logic layer
│   ├── auth_service.py        # Authentication service
│   ├── execution_service.py   # Execution business logic
│   ├── execution_processor.py # Execution processing logic
│   ├── execution_tasks.py     # Celery task definitions
│   ├── report_service.py      # Report generation
│   ├── storage_service.py     # Cloud storage abstraction
│   ├── celery_app.py          # Celery configuration
│   └── gemini_runtime.py      # Gemini AI runtime
├── processors/                # Evidence processing workers
├── scripts/                   # Processing scripts
│   ├── pre-processor/         # Data preprocessing
│   └── processor/             # Main processing logic
├── documentation/             # Setup guides & documentation
│   ├── README.md              # Documentation hub
│   ├── setup-mac.md           # macOS setup guide
│   ├── setup-ubuntu.md        # Ubuntu setup guide
│   ├── setup-docker.md        # Docker setup guide
│   ├── environment-setup.md   # Environment variables guide
│   ├── troubleshooting.md     # Troubleshooting guide
│   └── scripts/               # Helper automation scripts
├── main.py                    # FastAPI application entry point
├── celery_worker.py           # Celery worker entrypoint
├── requirements.txt           # Python dependencies
├── docker-compose.yml         # Docker orchestration
└── .env                       # Environment variables (create from .env.example)

evidence-analysis-portal-p1/
├── src/
│   ├── components/            # React components
│   │   ├── Layout.jsx
│   │   ├── executions/       # Execution-related components
│   │   ├── reports/          # Report components
│   │   └── ui/               # shadcn/ui components
│   ├── pages/                # Route pages
│   │   ├── Dashboard.jsx
│   │   ├── ExecutionList.jsx
│   │   ├── ExecutionDetail.jsx
│   │   └── Login.jsx
│   ├── services/             # API client services
│   │   ├── api.js
│   │   └── executionService.js
│   ├── context/              # React context
│   └── config/               # Configuration
├── package.json              # NPM dependencies
├── vite.config.js            # Vite configuration
└── tailwind.config.js        # Tailwind CSS configuration
```
</details>

---

<br>

## 👥 Team

The Evidence Analysis System is developed and maintained by a dedicated team committed to providing quality evidence analysis tools.

### Contributors

Contributions are welcome! Feel free to submit issues, feature requests, or pull requests.

---

<br>

## 📜 License & Support

### License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

### Support

🐛 **Issues**: Open an issue with error logs and system info  
📖 **Documentation**: Check the [documentation/](documentation/) folder for comprehensive guides  
💬 **Questions**: Review the [troubleshooting guide](documentation/troubleshooting.md) first

---

<br>

## 🛠️ Open Source Dependencies

This project is built with several open-source tools and dependencies that supported its development:

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![RabbitMQ](https://img.shields.io/badge/Rabbitmq-FF6600?style=for-the-badge&logo=rabbitmq&logoColor=white)
![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)

![React](https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB)
![TailwindCSS](https://img.shields.io/badge/tailwindcss-%2338B2AC.svg?style=for-the-badge&logo=tailwind-css&logoColor=white)
![Vite](https://img.shields.io/badge/vite-%23646CFF.svg?style=for-the-badge&logo=vite&logoColor=white)
![Chart.js](https://img.shields.io/badge/chart.js-F5788D.svg?style=for-the-badge&logo=chart.js&logoColor=white)

![Git](https://img.shields.io/badge/git-%23F05033.svg?style=for-the-badge&logo=git&logoColor=white)
![Google Cloud](https://img.shields.io/badge/GoogleCloud-%234285F4.svg?style=for-the-badge&logo=google-cloud&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)

---

<div align="center">

**Made with ❤️ by the Evidence Analysis Team**

</div>
