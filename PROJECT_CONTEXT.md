# Portfolio Tracker v2 - Project Context

## Deployment: ASUSTOR NAS

### Toegang
- **NAS IP:** 192.168.1.57
- **SSH alias:** `ssh nas` (geconfigureerd in `~/.ssh/config`)
- **SSH user:** jan
- **SSH wachtwoord:** Bredeweg9320
- **SSH key:** `~/.ssh/nas_ed25519`
- **Docker vereist sudo:** `echo 'Bredeweg9320' | sudo -S docker <command>`

### URLs
- **Frontend (dashboard):** http://192.168.1.57:5180/
- **Backend API:** http://192.168.1.57:8010/
- **Portainer (Docker UI):** http://192.168.1.57:19900/

### Poorten op NAS
| Service | Poort | Opmerking |
|---------|-------|-----------|
| Backend (FastAPI/Uvicorn) | 8010 | Host network |
| Frontend (Nginx) | 5180 | Host network |

### Netwerk: Host Mode (BELANGRIJK)
De ASUSTOR NAS heeft `ip_masquerade` uitgeschakeld op Docker bridge networks en geen iptables geïnstalleerd.
Dit betekent dat containers op bridge networks **geen internet toegang** hebben.

**Oplossing:** `network_mode: host` in docker-compose.nas.yml.

Gevolgen:
- Backend luistert direct op poort **8010** (via uvicorn `--port 8010` command override)
- Frontend/Nginx luistert direct op poort **5180** (via `nginx.nas.conf`)
- Nginx proxied `/api` naar `http://127.0.0.1:8010` (niet `backend:8000`)
- Aparte bestanden voor NAS: `Dockerfile.nas`, `nginx.nas.conf`, `docker-compose.nas.yml`

### Bestanden op NAS
- **Project root:** `/volume1/docker/portfolio-tracker/`
- **Docker compose:** `/volume1/docker/portfolio-tracker/docker-compose.nas.yml`
- **Database (SQLite):** `/volume1/docker/portfolio-tracker/data/portfolio.db`

### Container namen
- `portfolio-backend` (FastAPI + Uvicorn, poort 8010)
- `portfolio-frontend` (Nginx + React SPA, poort 5180)

### Deployment Procedure

```bash
# 1. Rsync code naar NAS
rsync -avz \
  --exclude=node_modules --exclude=.git --exclude=__pycache__ \
  --exclude='*.pyc' --exclude='.venv' --exclude='backend/venv' \
  --exclude='frontend/node_modules' --exclude='frontend/dist' \
  --exclude='PROJECT_CONTEXT.md' --exclude='PROJECT_STATUS.md' \
  --exclude='CLAUDE.md' --exclude='.claude' \
  --exclude='.github' --exclude='infra' \
  /Users/janderijck/Development/portfolio-tracker-v2/ nas:/volume1/docker/portfolio-tracker/

# 2. Build containers
ssh nas "echo 'Bredeweg9320' | sudo -S sh -c 'cd /volume1/docker/portfolio-tracker && docker compose -f docker-compose.nas.yml build --no-cache'"

# 3. Herstart containers
ssh nas "echo 'Bredeweg9320' | sudo -S sh -c 'cd /volume1/docker/portfolio-tracker && docker compose -f docker-compose.nas.yml up -d'"

# 4. Verificatie
ssh nas "echo 'Bredeweg9320' | sudo -S docker ps --format 'table {{.Names}}\t{{.Status}}' --filter 'name=portfolio'"
ssh nas "curl -s http://localhost:8010/"
ssh nas "curl -s -o /dev/null -w '%{http_code}' http://localhost:5180/"
ssh nas "curl -s --max-time 120 http://localhost:5180/api/portfolio | head -c 200"
```

### Logs bekijken

```bash
# Backend logs
ssh nas "echo 'Bredeweg9320' | sudo -S docker logs portfolio-backend --tail 50"

# Frontend/Nginx logs
ssh nas "echo 'Bredeweg9320' | sudo -S docker logs portfolio-frontend --tail 50"

# Live volgen
ssh nas "echo 'Bredeweg9320' | sudo -S docker logs -f portfolio-backend"
```

### Containers beheren

```bash
# Stop
ssh nas "echo 'Bredeweg9320' | sudo -S sh -c 'cd /volume1/docker/portfolio-tracker && docker compose -f docker-compose.nas.yml down'"

# Restart
ssh nas "echo 'Bredeweg9320' | sudo -S sh -c 'cd /volume1/docker/portfolio-tracker && docker compose -f docker-compose.nas.yml restart'"

# Status
ssh nas "echo 'Bredeweg9320' | sudo -S docker ps --filter 'name=portfolio'"
```

## Lokale Development

### Poorten (lokaal)
| Service | Poort |
|---------|-------|
| Frontend (Vite) | 5177 |
| Backend (FastAPI) | 8004 |

### Tech Stack
- **Backend:** Python 3.11, FastAPI, Uvicorn, SQLite
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query
- **Database:** SQLite (file-based, `/data/portfolio.db`)

## Architectuur
- **NAS:** Host networking, nginx proxied `/api` -> `localhost:8010`
- **Standaard/Azure:** Bridge networking, nginx proxied `/api` -> `backend:8000`
- SQLite database gemount als volume voor persistentie
- Frontend gebouwd als static SPA, geserveerd door Nginx
- NAS-specifieke bestanden: `docker-compose.nas.yml`, `frontend/Dockerfile.nas`, `frontend/nginx.nas.conf`
- Standaard bestanden: `docker-compose.yml`, `frontend/Dockerfile`, `frontend/nginx.simple.conf`

## Bekende Issues
- ASUSTOR NAS: Docker bridge networks hebben geen internet (ip_masquerade=false, geen iptables) → host networking vereist
- npm audit toont 16 vulnerabilities (4 moderate, 12 high) in frontend dependencies
- Vite chunk size warning (828kB bundle) - overweeg code-splitting
