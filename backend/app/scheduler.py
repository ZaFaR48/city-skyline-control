from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .services.ping_monitor import ping_all_stations
from .services.headscale import sync_headscale_nodes
from .services.operations_summary import run_operations_summary_job


def start_scheduler() -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone="UTC")
    sched.add_job(ping_all_stations, "interval", seconds=settings.PING_INTERVAL_SEC, id="ping_all")
    sched.add_job(sync_headscale_nodes, "interval", seconds=60, id="headscale_sync")
    sched.add_job(
        run_operations_summary_job,
        "interval",
        minutes=10,
        id="telegram_operations_summary",
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    return sched


def stop_scheduler(sched: AsyncIOScheduler) -> None:
    sched.shutdown(wait=False)
