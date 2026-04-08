---
name: service-scaffold
description: Scaffold a new Docker microservice following the project pattern. Creates Dockerfile, FastAPI main.py with health endpoint, requirements.txt, and docker-compose entry. Use when building any new service from the PRD service list.
---

## Service Scaffold Workflow

When scaffolding a new service (`$ARGUMENTS` = service name):

### 1. Validate Service Name
Check that the service name matches one from the PRD:
`gateway`, `slack-bot`, `rag-ingestion`, `cac-orchestrator`, `sync-mirror`, `sync-back`, `approval-ui`, `email-notifier`

### 2. Create Directory Structure
```
services/{name}/
  Dockerfile
  requirements.txt
  src/
    main.py
    __init__.py
```

### 3. Generate `src/main.py`
```python
"""
{Service Name} — Corporate AI Agent System
See PRD.md Section 8 for specification.
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown

app = FastAPI(title="{service-name}", lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "{service-name}"}
```

### 4. Generate `Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
EXPOSE {PORT}
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "{PORT}"]
```

### 5. Generate `requirements.txt`
Base: `fastapi>=0.111.0`, `uvicorn>=0.30.0`, `pydantic>=2.0.0`, `python-dotenv>=1.0.0`
Add service-specific deps from PRD Section 6.

### 6. Add to `docker-compose.yml`
Add the service entry with correct ports, volumes, depends_on, and network.
Follow data zone rules:
- Agent services: `mirror_data:/data/mirror:ro`
- Staging writers: `staging_data:/data/staging:rw`
- Only sync-mirror: `mirror_data:/data/mirror:rw`

### 7. Verify
- `docker compose build {service-name}`
- `docker compose up {service-name}`
- `curl http://localhost:{PORT}/health`

### Port Assignment
| Service | Port |
|---------|------|
| gateway | 3000 |
| cac-orchestrator | 3001 |
| slack-bot | 3003 |
| rag-ingestion | 3004 |
| approval-ui | 4000 |
| email-notifier | 3005 |
| sync-mirror | internal |
| sync-back | internal |
