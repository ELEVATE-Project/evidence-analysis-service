<div align="center">

# Evidence Analysis System

AI-powered platform for processing and analyzing CSV-based educational evidence data using Google Gemini, FastAPI, and React.

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
[![Python](https://img.shields.io/badge/python-3.12+-brightgreen.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2.0-61DAFB.svg)](https://react.dev/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

## Supported Operating Systems

- **Ubuntu** 20.04+
- **macOS** 12 Monterey+
- **Windows** 11+ (via WSL2)

---

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  React Frontend │─────▶│  FastAPI Backend │─────▶│   PostgreSQL    │
│   (Port 5173)   │◀─────│   (Port 6002)    │◀─────│   (Port 5432)   │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
              ┌──────────┐  ┌──────────┐  ┌──────────┐
              │ RabbitMQ │  │  Celery  │  │  GCP /   │
              │  Broker  │  │  Worker  │  │  AWS S3  │
              └──────────┘  └──────────┘  └──────────┘
```

**Backend**: FastAPI · PostgreSQL · Celery · RabbitMQ · SQLAlchemy · Google Gemini  
**Frontend**: React 18 · Vite · Tailwind CSS · shadcn/ui  
**Infrastructure**: Docker · Alembic · GCP / AWS S3

---

## Setup & Deployment

<details>
<summary><b>Docker Setup (Recommended)</b></summary>
<br>

- [macOS — Docker](documentation/setup-mac-docker.md)
- [Ubuntu — Docker](documentation/setup-ubuntu-docker.md)
- [Windows — Docker](documentation/setup-ubuntu-docker.md) (via WSL2, follow Ubuntu guide)

</details>

<details>
<summary><b>Native Setup</b></summary>
<br>

- [macOS — Native](documentation/setup-mac-native.md)
- [Ubuntu — Native](documentation/setup-ubuntu-native.md)
- [Windows — Native](documentation/setup-ubuntu-native.md) (via WSL2, follow Ubuntu guide)

</details>

---

## API Documentation

- **Swagger UI**: http://localhost:6002/docs — interactive API explorer
- **ReDoc**: http://localhost:6002/redoc — alternative reference
- **OpenAPI JSON**: http://localhost:6002/openapi.json

<details>
<summary>Key API Endpoints</summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/login` | Authenticate user |
| `GET`  | `/api/v1/auth/me` | Get current user |
| `POST` | `/api/v1/auth/logout` | Logout user |
| `GET`  | `/api/v1/executions` | List executions |
| `POST` | `/api/v1/executions` | Create execution |
| `GET`  | `/api/v1/executions/{id}` | Get execution details |
| `POST` | `/api/v1/executions/{id}/run` | Start AI processing |
| `PATCH`| `/api/v1/executions/{id}` | Update execution |
| `GET`  | `/api/v1/reports` | List reports |
| `GET`  | `/api/v1/reports/{id}/download` | Download report |
| `POST` | `/api/v1/cloud/signed-upload-url` | Get signed upload URL |
| `POST` | `/api/v1/cloud/signed-download-url` | Get signed download URL |

**Example**:
```bash
# Login
curl -X POST http://localhost:6002/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# List executions
curl http://localhost:6002/api/v1/executions \
  -H "Authorization: Bearer <token>"
```

</details>

---

## Service Ports

| Service | Port | URL | Credentials |
|---------|------|-----|-------------|
| Frontend | 5173 | http://localhost:5173 | admin / admin123 |
| Backend API | 8000 | http://localhost:8000 | — |
| API Docs | 8000 | http://localhost:6002/docs | — |
| PostgreSQL | 5432 | localhost:5432 | postgres / postgres |
| RabbitMQ | 5672 | AMQP | guest / guest |
| RabbitMQ UI | 15672 | http://localhost:15672 | guest / guest |
| Redis (optional) | 6379 | localhost:6379 | — |

⚠️ Change default passwords before production deployment.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Documentation Hub](documentation/README.md) | Full setup index and checklist |
| [Environment Variables](documentation/environment-setup.md) | Complete `.env` reference |
| [Troubleshooting](documentation/troubleshooting.md) | Common issues and fixes |
| [Migration Workflow](documentation/migration-workflow.md) | Alembic migration reference |

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Made with ❤️ by the Evidence Analysis Team**

</div>
