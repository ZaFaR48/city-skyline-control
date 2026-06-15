from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import (
    alerts, analytics, auth, cameras, headscale, ping, rustdesk, stations, webhooks,
)
from .scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    sched = start_scheduler()
    try:
        yield
    finally:
        stop_scheduler(sched)


app = FastAPI(
    title="City Parking Control Center API",
    version="1.0.0",
    description="Manage parking stations, cameras, VPN nodes and remote-desktop clients.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/api/auth",       tags=["auth"])
app.include_router(stations.router,  prefix="/api/stations",   tags=["stations"])
app.include_router(cameras.router,   prefix="/api/cameras",    tags=["cameras"])
app.include_router(alerts.router,    prefix="/api/alerts",     tags=["alerts"])
app.include_router(headscale.router, prefix="/api/headscale",  tags=["headscale"])
app.include_router(rustdesk.router,  prefix="/api/rustdesk",   tags=["rustdesk"])
app.include_router(ping.router,      prefix="/api/ping",       tags=["ping"])
app.include_router(analytics.router, prefix="/api/analytics",  tags=["analytics"])
app.include_router(webhooks.router,  prefix="/api/webhooks",   tags=["webhooks"])


@app.get("/api/health", tags=["meta"])
async def health():
    return {"status": "ok"}
