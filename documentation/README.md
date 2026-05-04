# Documentation - Evidence Analysis System

Welcome to the Evidence Analysis System documentation! This folder contains comprehensive guides for setting up, configuring, deploying, and troubleshooting the system.

---

## 📚 Documentation Index

### Setup Guides

| Guide | Description | Best For |
|-------|-------------|----------|
| [macOS Setup](setup-mac.md) | Complete installation guide for macOS (Monterey+) | macOS developers |
| [Ubuntu Setup](setup-ubuntu.md) | Step-by-step setup for Ubuntu (20.04/22.04/24.04) | Linux developers |
| [Docker Setup](setup-docker.md) | Containerized deployment guide | Production, teams |

### Configuration

| Guide | Description |
|-------|-------------|
| [Environment Setup](environment-setup.md) | Complete reference for all environment variables |
| [Troubleshooting](troubleshooting.md) | Solutions for common issues and errors |

### Docker Files

| File | Description |
|------|-------------|
| [Dockerfile](Dockerfile) | Production-ready Docker image definition |
| [docker-compose.prod.yml](docker-compose.prod.yml) | Production Docker Compose orchestration |

### Helper Scripts

All scripts are located in the `scripts/` directory and are ready to use.

| Script | Purpose | Usage |
|--------|---------|-------|
| [setup.sh](scripts/setup.sh) | Automated setup and installation | `./setup.sh` |
| [start.sh](scripts/start.sh) | Start all services | `./start.sh` |
| [stop.sh](scripts/stop.sh) | Stop all services | `./stop.sh` |
| [reset-db.sh](scripts/reset-db.sh) | Reset database (⚠️ deletes all data) | `./reset-db.sh` |
| [health-check.sh](scripts/health-check.sh) | Verify all services are running | `./health-check.sh` |

---

## 🚀 Quick Start

### For First-Time Setup

Choose your platform:

```bash
# macOS
See: setup-mac.md

# Ubuntu
See: setup-ubuntu.md

# Docker (all platforms)
See: setup-docker.md
```

### Using Helper Scripts (After Initial Setup)

```bash
# Navigate to scripts directory
cd documentation/scripts

# Start all services
./start.sh

# Check health
./health-check.sh

# Stop all services
./stop.sh
```

---

## 📋 Setup Checklist

Use this checklist to ensure your setup is complete:

### Prerequisites
- [ ] Python 3.12 installed
- [ ] Node.js 16+ installed
- [ ] PostgreSQL 14+ installed and running
- [ ] RabbitMQ 3.13+ installed and running
- [ ] Docker + Docker Compose installed (for Docker setup)

### Backend Setup
- [ ] Virtual environment created
- [ ] Python dependencies installed
- [ ] `.env` file configured
- [ ] Database initialized
- [ ] Default users seeded
- [ ] Migrations applied
- [ ] Backend API running (http://localhost:8000)
- [ ] Celery worker running

### Frontend Setup
- [ ] npm dependencies installed
- [ ] `.env` file configured
- [ ] Development server running (http://localhost:5173)

### Verification
- [ ] API health check passes
- [ ] Database connection successful
- [ ] RabbitMQ management UI accessible
- [ ] Can log in with default credentials
- [ ] End-to-end test successful

---

## 🔧 Configuration Overview

### Required Environment Variables

#### Backend (Minimum)
```env
DATABASE_URL=postgresql://user:pass@host:5432/db
JWT_SECRET_KEY=your-secret-key
GEMINI_API_KEY_1=your-api-key
CLOUD_STORAGE_PROVIDER=gcp|aws
CLOUD_STORAGE_BUCKETNAME=your-bucket
CELERY_BROKER_URL=amqp://guest:guest@host:5672//
```

#### Frontend (Minimum)
```env
APPLICATION_PORT=5173
API_ENDPOINT=http://localhost:8000
```

**Full reference**: [environment-setup.md](environment-setup.md)

---

## 🐛 Troubleshooting

Encountering issues? Check our comprehensive troubleshooting guide:

- [Installation Issues](troubleshooting.md#installation-issues)
- [Database Issues](troubleshooting.md#database-issues)
- [Backend API Issues](troubleshooting.md#backend-api-issues)
- [Frontend Issues](troubleshooting.md#frontend-issues)
- [RabbitMQ & Celery Issues](troubleshooting.md#rabbitmq--celery-issues)
- [Cloud Storage Issues](troubleshooting.md#cloud-storage-issues)
- [Docker Issues](troubleshooting.md#docker-issues)

**Quick health check**:
```bash
cd documentation/scripts
./health-check.sh
```

---

## 🏗️ Architecture Overview

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
              │ RabbitMQ │  │  Celery  │  │   GCP/   │
              │  Broker  │  │  Worker  │  │   S3     │
              └──────────┘  └──────────┘  └──────────┘
```

---

## 📦 Service Ports

| Service | Port | Purpose |
|---------|------|---------|
| Frontend | 5173 | React development server |
| Backend API | 8000 | FastAPI REST API |
| PostgreSQL | 5432 | Database server |
| RabbitMQ | 5672 | Message broker (AMQP) |
| RabbitMQ Management | 15672 | Web UI (guest/guest) |
| Redis | 6379 | Cache (optional) |

---

## 🔐 Default Credentials

### Application Users

After running `seed_data.py`:

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Administrator |
| program_designer | user123 | Program Designer |
| analyst | user123 | Analyst |

⚠️ **Security**: Change these passwords in production!

### Services

| Service | Username | Password |
|---------|----------|----------|
| PostgreSQL | postgres | postgres (configurable) |
| RabbitMQ | guest | guest |

---

## 📚 Additional Resources

### Main Documentation
- [Main README](../README.md) - Project overview and quick start
- [Frontend README](../../evidence-analysis-portal-p1/README.md) - Frontend-specific setup

### External Links
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Documentation](https://docs.docker.com/)
- [Google Gemini AI](https://ai.google.dev/)

---

## 🆘 Getting Help

1. **Check Documentation**: Review the relevant setup guide for your OS
2. **Run Health Check**: Use `./health-check.sh` to diagnose issues
3. **Review Logs**: Check application logs for errors
4. **Troubleshooting Guide**: See [troubleshooting.md](troubleshooting.md)
5. **Open an Issue**: If problem persists, open an issue with:
   - Error messages
   - System information
   - Steps to reproduce
   - Log excerpts (sanitized)

---

## 🔄 Update Process

To update your installation:

```bash
# Update code
git pull origin main

# Backend updates
cd evidence-analysis-service-p1
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# Frontend updates
cd ../evidence-analysis-portal-p1
npm install

# Restart services
cd ../evidence-analysis-service-p1/documentation/scripts
./stop.sh
./start.sh
```

---

## 📝 Contributing

When contributing to documentation:

1. **Keep it simple**: Write for beginners
2. **Test instructions**: Verify all commands work
3. **Be specific**: Include exact commands, not general descriptions
4. **Add examples**: Show real-world usage
5. **Update index**: Add new docs to this README

---

## 📄 Documentation Standards

All documentation follows these principles:

- ✅ **Clear and concise** - No unnecessary jargon
- ✅ **Step-by-step** - Sequential instructions with exact commands
- ✅ **OS-specific** - Separate instructions for macOS, Ubuntu, Windows
- ✅ **Tested** - All commands verified on target platforms
- ✅ **Complete** - No assumed knowledge or missing steps
- ✅ **Updated** - Kept in sync with code changes

---

## 🗺️ Documentation Structure

```
documentation/
├── README.md                    # This file - documentation index
├── setup-mac.md                 # macOS setup guide
├── setup-ubuntu.md              # Ubuntu setup guide
├── setup-docker.md              # Docker setup guide
├── environment-setup.md         # Environment variables reference
├── troubleshooting.md           # Troubleshooting guide
├── Dockerfile                   # Production Docker image
├── docker-compose.prod.yml      # Production Docker Compose
└── scripts/                     # Helper scripts
    ├── setup.sh                 # Automated setup
    ├── start.sh                 # Start all services
    ├── stop.sh                  # Stop all services
    ├── reset-db.sh              # Reset database
    └── health-check.sh          # Health check
```

---

**Last Updated**: April 30, 2026  
**Version**: 1.0.0  
**Maintained By**: Evidence Analysis Team

---

**Ready to start?** Choose your setup guide:
- [macOS Setup](setup-mac.md)
- [Ubuntu Setup](setup-ubuntu.md)
- [Docker Setup](setup-docker.md)
