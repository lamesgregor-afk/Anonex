import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import settings
from app_state import app_state
from database.db import Database
from handlers import main_router
from handlers.middlewares import UserMiddleware, ThrottleMiddleware
from scheduler import create_scheduler
from services.crypto_service import close_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _build_storage():
    if settings.REDIS_URL:
        try:
            from aiogram.fsm.storage.redis import RedisStorage
            storage = RedisStorage.from_url(settings.REDIS_URL)
            logger.info("[Storage] Using Redis: %s", settings.REDIS_URL)
            return storage
        except ImportError:
            logger.warning("[Storage] redis not installed, using MemoryStorage")
    from aiogram.fsm.storage.memory import MemoryStorage
    logger.info("[Storage] Using MemoryStorage (FSM lost on restart)")
    return MemoryStorage()


async def main():
    await Database.init()
    logger.info("[DB] Initialized.")

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    bot_info = await bot.get_me()
    if not bot_info.username:
        logger.error("[Bot] Bot has no username. Set it via @BotFather.")
        await bot.session.close()
        return
    app_state.set_bot_username(bot_info.username)
    logger.info("[Bot] @%s started.", app_state.bot_username)

    storage = _build_storage()
    dp = Dispatcher(storage=storage)

    dp.message.middleware(ThrottleMiddleware(rate=5, period=3.0))
    dp.callback_query.middleware(ThrottleMiddleware(rate=10, period=3.0))
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())

    dp.include_router(main_router)

    scheduler = create_scheduler(bot)
    scheduler.start()
    logger.info("[Scheduler] Started.")

    if settings.WEBHOOK_URL:
        await _run_webhook(bot, dp, scheduler)
    else:
        await _run_polling(bot, dp, scheduler)


async def _run_polling(bot: Bot, dp: Dispatcher, scheduler):
    logger.info("[Polling] Starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await close_session()
        await bot.session.close()


async def _run_webhook(bot: Bot, dp: Dispatcher, scheduler):
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    webhook_path = "/webhook"
    base = settings.WEBHOOK_URL.strip().rstrip("/")
    if not base.startswith(("https://", "http://")):
        logger.error("[Webhook] WEBHOOK_URL must start with https:// — got %r", base)
        raise SystemExit(1)
    webhook_url = f"{base}{webhook_path}"
    logger.info("[Webhook] Setting to %s", webhook_url)

    await bot.set_webhook(
        webhook_url,
        drop_pending_updates=True,
        allowed_updates=dp.resolve_used_update_types(),
    )

    app = web.Application()

    async def healthz(request):
        return web.Response(text="ok")
    app.router.add_get("/healthz", healthz)

    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.PORT)
    await site.start()
    logger.info("[Server] 0.0.0.0:%d", settings.PORT)

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)
        await close_session()
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
