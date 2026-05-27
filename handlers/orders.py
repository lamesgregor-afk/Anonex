import logging
from html import escape
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import fmt
from app_state import app_state
from services.listing_service import ListingService
from services.order_service import OrderService
from services.user_service import UserService
from services.crypto_service import CryptoService
from config import settings
from .keyboards import (
    order_pay_button,
    buyer_delivery_keyboard,
    seller_deliver_button,
    main_menu,
)

logger = logging.getLogger(__name__)
router = Router()

STATUS_LABELS = {
    "pending_payment": "⏳ Ожидает оплаты",
    "paid": "💰 Оплачен (ждём доставки)",
    "delivered": "📦 Доставлен (подтверди)",
    "confirmed": "✅ Завершён",
    "paid_out": "✅ Выплачен",
    "disputed": "⚠️ Спор",
    "cancelled": "❌ Отменён",
    "refunded": "↩️ Возврат",
}


class DeliverState(StatesGroup):
    order_id = State()
    note = State()


class DisputeState(StatesGroup):
    reason = State()


# ─── Покупка ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("buy:"))
async def buy_listing(callback: CallbackQuery, user: dict, bot: Bot):
    listing_id = int(callback.data.split(":")[1])
    listing = await ListingService.get_by_id(listing_id)

    if not listing or not listing["is_active"]:
        await callback.answer("Объявление недоступно.", show_alert=True)
        return
    if listing["seller_id"] == user["id"]:
        await callback.answer("Нельзя купить у самого себя.", show_alert=True)
        return

    # Защита от дубль-ордера
    if await OrderService.has_active_order_for_listing(user["id"], listing_id):
        await callback.answer("У тебя уже есть активный заказ на этот товар.", show_alert=True)
        return

    referrer = await UserService.get_referrer(user["id"])
    order = await OrderService.create(
        listing_id=listing_id,
        buyer_id=user["id"],
        seller_id=listing["seller_id"],
        amount_micro=listing["price"],
        has_referrer=referrer is not None,
    )

    invoice = await CryptoService.create_invoice(
        amount_micro=listing["price"],
        order_id=order["id"],
        description=f"{listing['title'][:50]} — GhostMarket #{order['id']}",
        bot_username=app_state.bot_username,
    )
    if not invoice:
        await OrderService.try_mark_cancelled(order["id"])
        await callback.answer("Ошибка создания инвойса. Попробуй позже.", show_alert=True)
        return

    await OrderService.set_invoice(order["id"], invoice["invoice_id"], invoice["pay_url"])

    await callback.message.answer(
        f"🛒 <b>Заказ #{order['id']}</b>\n\n"
        f"Товар: <b>{escape(listing['title'])}</b>\n"
        f"Сумма: <b>{fmt(listing['price'])} USDT</b>\n"
        f"Комиссия: {fmt(order['fee'])} USDT (10%)\n\n"
        f"Оплати через CryptoBot, затем нажми «Проверить оплату».",
        reply_markup=order_pay_button(invoice["pay_url"], order["id"]),
    )
    await callback.answer()


# ─── Проверка оплаты ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("check_pay:"))
async def check_payment(callback: CallbackQuery, user: dict, bot: Bot):
    order_id = int(callback.data.split(":")[1])
    order = await OrderService.get_by_id(order_id)

    if not order or order["buyer_id"] != user["id"]:
        await callback.answer("Заказ не найден.", show_alert=True)
        return
    if order["status"] != "pending_payment":
        await callback.answer(STATUS_LABELS.get(order["status"], order["status"]), show_alert=True)
        return

    invoice = await CryptoService.get_invoice(order["crypto_invoice_id"])
    if not invoice:
        await callback.answer("Не удалось проверить. Попробуй позже.", show_alert=True)
        return
    if invoice["status"] != "paid":
        await callback.answer("Оплата ещё не поступила.", show_alert=True)
        return

    changed = await OrderService.try_mark_paid(order_id)
    if not changed:
        await callback.answer("Уже обработан.", show_alert=True)
        return

    await OrderService.log_transaction(
        user_id=user["id"], tx_type="escrow_in",
        amount_micro=order["amount"], order_id=order_id,
        comment=f"Escrow for order #{order_id}",
    )

    seller = await UserService.get_by_id(order["seller_id"])
    if seller:
        try:
            await bot.send_message(
                seller["tg_id"],
                f"💰 <b>Новая сделка #{order_id}</b>\n"
                f"Сумма: {fmt(order['amount'])} USDT → тебе {fmt(order['net_to_seller'])} USDT\n"
                f"Передай товар покупателю:",
                reply_markup=seller_deliver_button(order_id),
            )
        except Exception:
            pass

    await callback.message.edit_text(
        f"✅ <b>Оплата подтверждена!</b>\n"
        f"Заказ #{order_id} в эскроу. Жди товар от продавца.",
    )
    await callback.answer()


# ─── Отмена ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cancel_order:"))
async def cancel_order(callback: CallbackQuery, user: dict):
    order_id = int(callback.data.split(":")[1])
    order = await OrderService.get_by_id(order_id)
    if not order or order["buyer_id"] != user["id"]:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    if not await OrderService.try_mark_cancelled(order_id):
        await callback.answer("Отменить можно только неоплаченный заказ.", show_alert=True)
        return
    await callback.message.edit_text(f"❌ Заказ #{order_id} отменён.")
    await callback.answer()


# ─── Мои покупки ─────────────────────────────────────────────────────────────

@router.message(F.text == "📦 Мои покупки")
async def my_purchases(message: Message, user: dict):
    orders = await OrderService.get_buyer_orders(user["id"], limit=10)
    if not orders:
        await message.answer("У тебя ещё нет покупок.")
        return
    for order in orders:
        title = order.get("listing_title") or f"Товар #{order['listing_id']}"
        text = (
            f"📦 <b>{escape(title)}</b>\n"
            f"#{order['id']} | {fmt(order['amount'])} USDT | "
            f"{STATUS_LABELS.get(order['status'], order['status'])}"
        )
        kb = buyer_delivery_keyboard(order["id"]) if order["status"] == "delivered" else None
        await message.answer(text, reply_markup=kb)


# ─── Доставка продавцом ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("deliver:"))
async def start_deliver(callback: CallbackQuery, state: FSMContext, user: dict):
    order_id = int(callback.data.split(":")[1])
    order = await OrderService.get_by_id(order_id)
    if not order or order["seller_id"] != user["id"]:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    if order["status"] != "paid":
        await callback.answer("Нельзя передать в текущем статусе.", show_alert=True)
        return
    await state.set_state(DeliverState.note)
    await state.update_data(order_id=order_id)
    await callback.message.answer(
        f"📤 <b>Заказ #{order_id}</b>\n"
        f"Отправь товар/ссылку/код. Сообщение уйдёт покупателю анонимно.",
    )
    await callback.answer()


@router.message(DeliverState.note)
async def deliver_note(message: Message, state: FSMContext, user: dict, bot: Bot):
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await state.clear()
        return

    order = await OrderService.get_by_id(order_id)
    if not order or order["seller_id"] != user["id"] or order["status"] != "paid":
        await state.clear()
        await message.answer("Статус заказа изменился. Передача невозможна.")
        return

    delivery_note = (message.text or "[файл]").strip()[:500]
    changed = await OrderService.try_mark_delivered(order_id, delivery_note)
    if not changed:
        await state.clear()
        await message.answer("Статус уже изменился.")
        return
    await state.clear()

    buyer = await UserService.get_by_id(order["buyer_id"])
    if buyer:
        try:
            if message.document or message.photo or message.video or message.audio:
                await message.copy_to(buyer["tg_id"])
                await bot.send_message(
                    buyer["tg_id"],
                    f"📦 <b>Товар по заказу #{order_id} доставлен.</b>\n"
                    f"Подтверди получение или открой спор.",
                    reply_markup=buyer_delivery_keyboard(order_id),
                )
            else:
                await bot.send_message(
                    buyer["tg_id"],
                    f"📦 <b>Товар по заказу #{order_id}:</b>\n\n{escape(delivery_note)}",
                    reply_markup=buyer_delivery_keyboard(order_id),
                )
        except Exception:
            pass

    await message.answer(f"✅ Передано. Ждём подтверждения (авто через 48ч).")


# ─── Подтверждение покупателем ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("confirm:"))
async def confirm_receipt(callback: CallbackQuery, user: dict, bot: Bot):
    order_id = int(callback.data.split(":")[1])
    order = await OrderService.get_by_id(order_id)
    if not order or order["buyer_id"] != user["id"]:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    changed = await OrderService.try_mark_confirmed(order_id)
    if not changed:
        await callback.answer("Статус уже изменился.", show_alert=True)
        return

    order = await OrderService.get_by_id(order_id)
    await release_funds(order, bot)

    await callback.message.edit_text(f"✅ Заказ #{order_id} завершён. Спасибо!")
    await callback.answer()


async def release_funds(order: dict, bot: Bot):
    """
    Начисляет продавцу (pending), рефереру (balance+total_earned), логирует.
    Помечает funds_released=1 — без этого scheduler не разморозит pending.
    Идемпотентна: mark_funds_released сработает только один раз.
    """
    # Проверяем идемпотентность — если уже released, выходим
    released = await OrderService.mark_funds_released(order["id"])
    if not released:
        logger.debug("[release_funds] order #%d already released", order["id"])
        return

    seller = await UserService.get_by_id(order["seller_id"])
    if not seller:
        return

    # Продавцу — в pending (hold 7 дней)
    await UserService.add_pending(seller["id"], order["net_to_seller"])
    await OrderService.log_transaction(
        user_id=seller["id"], tx_type="escrow_release",
        amount_micro=order["net_to_seller"], order_id=order["id"],
        comment="Escrow → seller pending",
    )

    # Реферальное — сразу на баланс + total_earned
    if order["referral_fee"] > 0:
        referrer = await UserService.get_referrer(order["buyer_id"])
        if referrer:
            await UserService.add_earned_balance(referrer["id"], order["referral_fee"])
            await OrderService.log_transaction(
                user_id=referrer["id"], tx_type="referral",
                amount_micro=order["referral_fee"], order_id=order["id"],
                comment=f"Referral from #{order['id']}",
            )
            try:
                await bot.send_message(
                    referrer["tg_id"],
                    f"💸 Реферальное: <b>+{fmt(order['referral_fee'])} USDT</b> (сделка #{order['id']})",
                )
            except Exception:
                pass

    # Лог комиссии платформы
    platform_fee = order["fee"] - order["referral_fee"]
    if platform_fee > 0:
        await OrderService.log_transaction(
            user_id=seller["id"], tx_type="fee",
            amount_micro=platform_fee, order_id=order["id"],
            comment="Platform fee",
        )

    try:
        await bot.send_message(
            seller["tg_id"],
            f"🎉 <b>Сделка #{order['id']} завершена!</b>\n"
            f"+{fmt(order['net_to_seller'])} USDT (вывод через 7 дней)",
        )
    except Exception:
        pass


# ─── Спор ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("dispute:"))
async def open_dispute_start(callback: CallbackQuery, state: FSMContext, user: dict):
    order_id = int(callback.data.split(":")[1])
    order = await OrderService.get_by_id(order_id)
    if not order or order["buyer_id"] != user["id"]:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    if order["status"] not in ("delivered", "paid"):
        await callback.answer("Спор можно открыть только по активному заказу.", show_alert=True)
        return
    await state.set_state(DisputeState.reason)
    await state.update_data(order_id=order_id)
    await callback.message.answer(
        f"⚠️ <b>Спор по заказу #{order_id}</b>\nОпиши проблему:",
    )
    await callback.answer()


@router.message(DisputeState.reason)
async def open_dispute_reason(message: Message, state: FSMContext, user: dict, bot: Bot):
    if not message.text:
        await message.answer("Опиши проблему текстом.")
        return
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await state.clear()
        return

    reason = message.text.strip()[:1000]
    opened = await OrderService.open_dispute(order_id, user["id"], reason)
    await state.clear()

    if not opened:
        await message.answer("Не удалось открыть спор (статус изменился).", reply_markup=main_menu())
        return

    for admin_id in settings.get_admin_ids():
        try:
            await bot.send_message(
                admin_id,
                f"⚠️ <b>Спор — Заказ #{order_id}</b>\n"
                f"Покупатель: <code>{escape(user['ghost_id'])}</code>\n"
                f"Причина: {escape(reason[:300])}",
            )
        except Exception:
            pass

    await message.answer("⚠️ Спор открыт. Деньги заморожены до решения.", reply_markup=main_menu())
