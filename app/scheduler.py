import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings

log = structlog.get_logger(__name__)


def create_scheduler(client, bot, notifier) -> AsyncIOScheduler:
    from app.services.price_tracker import run_check

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_check,
        trigger=IntervalTrigger(hours=settings.check_interval_hours),
        args=[client, bot, notifier],
        id="price_check",
        replace_existing=True,
        misfire_grace_time=300,
    )
    log.info("scheduler_configured", interval_hours=settings.check_interval_hours)
    return scheduler
