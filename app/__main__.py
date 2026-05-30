import asyncio
import sys

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent
from apscheduler.events import EVENT_JOB_ERROR

from app.config import settings
from app.db.session import engine
from app.log_setup import configure_logging
from app.middlewares.db import DbSessionMiddleware
from app.middlewares.user_registration import UserRegistrationMiddleware
from app.ryanair.airports import load_airports
from app.ryanair.client import RyanairClient
from app.scheduler import create_scheduler
from app.services.alerting import set_alert_sink
from app.services.notifier import Notifier

from app.handlers import start, add_subscription, list_subscriptions, admin

log = structlog.get_logger(__name__)


async def main() -> None:
    configure_logging(settings.log_level, json_format=settings.log_json)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    client = RyanairClient()
    notifier = Notifier(bot)

    set_alert_sink(notifier.notify_admin)

    dp.update.outer_middleware(DbSessionMiddleware())
    dp.update.outer_middleware(UserRegistrationMiddleware())

    dp.include_router(start.router)
    dp.include_router(add_subscription.router)
    dp.include_router(list_subscriptions.router)
    dp.include_router(admin.router)

    @dp.errors()
    async def on_unhandled_error(event: ErrorEvent) -> bool:
        log.error(
            "unhandled_update_exception",
            update_id=event.update.update_id,
            exc_info=event.exception,
        )
        return True

    scheduler = create_scheduler(client, bot, notifier)

    def _on_job_error(evt) -> None:
        log.error("scheduled_job_failed", job_id=evt.job_id, exc_info=evt.exception)

    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    @dp.startup()
    async def on_startup() -> None:
        log.info("bot_starting")
        await load_airports(client)
        scheduler.start()
        log.info("bot_ready")

    @dp.shutdown()
    async def on_shutdown() -> None:
        scheduler.shutdown(wait=False)
        await client.aclose()
        await engine.dispose()
        log.info("bot_stopped")

    await dp.start_polling(bot, ryanair_client=client, notifier=notifier)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
