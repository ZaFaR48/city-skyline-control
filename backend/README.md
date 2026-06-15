# City Parking Control Center — FastAPI Backend

Production-ready scaffold for the backend that powers the React dashboard.

## Stack
- **FastAPI** 0.115 (async)
- **SQLAlchemy 2.x** + **asyncpg** (PostgreSQL)
- **Alembic** migrations
- **JWT** authentication with role-based access control (admin / operator / viewer)
- **APScheduler** for ping monitoring + Headscale auto-discovery
- **httpx** for Headscale / Telegram / n8n integration
- **uvicorn** for serving

## Folder structure
```
backend/
├── app/
│   ├── main.py              # FastAPI app factory, CORS, lifespan
│   ├── config.py            # Pydantic settings (env vars)
│   ├── database.py          # async engine + session
│   ├── deps.py              # auth/role dependencies
│   ├── security.py          # JWT + password hashing
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic request/response models
│   ├── routers/
│   │   ├── auth.py
│   │   ├── stations.py
│   │   ├── cameras.py
│   │   ├── alerts.py
│   │   ├── headscale.py
│   │   ├── rustdesk.py
│   │   ├── ping.py
│   │   ├── analytics.py
│   │   └── webhooks.py
│   ├── services/
│   │   ├── ping_monitor.py  # async ping every N seconds
│   │   ├── headscale.py     # discover nodes via Headscale API
│   │   ├── telegram.py      # send alerts
│   │   └── n8n.py           # forward events
│   └── scheduler.py
├── alembic/                 # migrations
├── alembic.ini
├── requirements.txt
├── .env.example
└── Dockerfile
```

## Quick start
```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Environment variables (`.env`)
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/parking
JWT_SECRET=change-me-to-32+chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_TTL_MIN=60
HEADSCALE_URL=http://headscale:8080
HEADSCALE_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
N8N_WEBHOOK_URL=
PING_INTERVAL_SEC=30
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

## API endpoints (summary)
| Method | Path | Roles |
|---|---|---|
| POST | `/api/auth/login` | public |
| POST | `/api/auth/refresh` | public |
| GET  | `/api/me` | any |
| GET  | `/api/stations` | any |
| POST | `/api/stations` | admin |
| PATCH| `/api/stations/{id}` | admin, operator |
| DELETE| `/api/stations/{id}` | admin |
| GET  | `/api/cameras` | any |
| POST | `/api/cameras` | admin |
| GET  | `/api/alerts` | any |
| POST | `/api/alerts/{id}/ack` | admin, operator |
| GET  | `/api/headscale/nodes` | any |
| POST | `/api/headscale/sync` | admin |
| GET  | `/api/rustdesk` | any |
| GET  | `/api/ping/{station_id}` | any |
| GET  | `/api/analytics/summary` | any |
| POST | `/api/webhooks/n8n/test` | admin |

All non-public routes require `Authorization: Bearer <jwt>`.

## Notes
- Run `alembic revision --autogenerate -m "msg"` after model changes.
- The `services/ping_monitor.py` task pings every station's VPN IP and writes
  to `ping_history`; on consecutive failures it inserts an `alerts` row and
  notifies Telegram + n8n.
- Headscale discovery runs on the same scheduler and inserts unknown nodes
  into the `headscale_nodes` table so they appear in the dashboard automatically.
