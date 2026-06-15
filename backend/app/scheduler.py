from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .services.ping_monitor import ping_all_stations
from .services.headscale import sync_headscale_nodes


def start_scheduler() -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone="UTC")
    sched.add_job(ping_all_stations, "interval", seconds=settings.PING_INTERVAL_SEC, id="ping_all")
    sched.add_job(sync_headscale_nodes, "interval", seconds=60, id="headscale_sync")
    sched.start()
    return sched


def stop_scheduler(sched: AsyncIOScheduler) -> None:
    sched.shutdown(wait=False)
