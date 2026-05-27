import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from services.order_service import OrderService
from services.user_service import UserService
from database.db import fmt

logger = logging.getLogger(__name__)


async def auto_confirm_orders(bot: Bot):
    """Авто-подтверждение через 48ч молчания покупателя."""
    orders = await OrderService.get_overdue_auto_confirm()
    if not orders:
        return

    from handlers.orders import release_funds

    for order in orders:
        changed = await OrderService.try_mark_confirmed(order["id"])
        if not changed:
            continue
        try:
            fresh = await OrderService.get_by_id(order["id"])
            await release_funds(fresh, bot)

            buyer = await UserService.get_by_id(order["buyer_id"])
            if buyer:
                try:
                    await bot.send_message(buyer["tg_id"],
                        f"⏰ Заказ #{order['id']} авто-подтверждён (48ч).")
                except Exception:
                    pass
            logger.info("[sched] Auto-confirmed #%d", order["id"])
        except Exception:
            logger.exception("[sched] auto_confirm error #%d", order["id"])


async def recover_unreleased(bot: Bot):
    """
    Recovery: если confirmed но funds_released=0 — значит был крэш
    между mark_confirmed и release_funds. Добиваем.
    """
    from handlers.orders import release_funds

    orders = await OrderService.get_unreleased_confirmed()
    for order in orders:
        try:
            await release_funds(order, bot)
            logger.info("[sched] Recovered release for #%d", order["id"])
        except Exception:
            logger.exception("[sched] recover error #%d", order["id"])


async def unlock_pending_balances(bot: Bot):
    """Разморозка pending → balance после 7-дневного hold."""
    orders = await OrderService.get_payout_ready()
    if not orders:
        return

    for order in orders:
        result = await OrderService.try_mark_paid_out_atomic(order["id"])
        if not result:
            continue
        try:
            ok = await UserService.move_pending_to_balance(
                order["seller_id"], order["net_to_seller"]
            )
            if not ok:
                logger.warning("[sched] move_pending failed for #%d", order["id"])
                continue

            seller = await UserService.get_by_id(order["seller_id"])
            if seller:
                try:
                    await bot.send_message(seller["tg_id"],
                        f"🔓 <b>Разблокировано!</b> Заказ #{order['id']}: "
                        f"+{fmt(order['net_to_seller'])} USDT доступно для вывода.")
                except Exception:
                    pass
            logger.info("[sched] Unlocked #%d", order["id"])
        except Exception:
            logger.exception("[sched] unlock error #%d", order["id"])


def create_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        auto_confirm_orders, "interval", minutes=15,
        kwargs={"bot": bot}, id="auto_confirm",
        replace_existing=True, max_instances=1,
    )
    scheduler.add_job(
        recover_unreleased, "interval", minutes=5,
        kwargs={"bot": bot}, id="recover_unreleased",
        replace_existing=True, max_instances=1,
    )
    scheduler.add_job(
        unlock_pending_balances, "interval", hours=1,
        kwargs={"bot": bot}, id="unlock_balances",
        replace_existing=True, max_instances=1,
    )

    return scheduler
