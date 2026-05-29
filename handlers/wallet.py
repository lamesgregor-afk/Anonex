import re
import logging
from html import escape
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import get_db, to_micro, fmt, transaction
from services.user_service import UserService
from services.order_service import OrderService
from config import settings
from .keyboards import wallet_keyboard, main_menu

logger = logging.getLogger(__name__)
router = Router()

MIN_WITHDRAWAL_MICRO = to_micro(1.0)

_TRC20_RE = re.compile(r'^T[A-Za-z0-9]{33}$')
_TG_ID_RE = re.compile(r'^\d{5,12}$')


def _validate_wallet(addr: str) -> bool:
    return bool(_TRC20_RE.match(addr) or _TG_ID_RE.match(addr))


class WithdrawState(StatesGroup):
    amount = State()
    wallet = State()


@router.message(F.text == "💼 Кошелёк")
async def show_wallet(message: Message, user: dict):
    fresh = await UserService.get_by_id(user["id"])
    await message.answer(
        f"💼 <b>Кошелёк</b>\n\n"
        f"Доступно: <b>{fmt(fresh['balance'])} USDT</b>\n"
        f"Заморожено: <b>{fmt(fresh['pending_balance'])} USDT</b> ⏳\n"
        f"Заработано всего: {fmt(fresh['total_earned'])} USDT\n\n"
        f"<i>Заморозка снимается через 7 дней.</i>",
        reply_markup=wallet_keyboard(),
    )


@router.callback_query(F.data == "withdraw")
async def withdraw_start(callback: CallbackQuery, state: FSMContext, user: dict):
    fresh = await UserService.get_by_id(user["id"])
    if fresh["balance"] < MIN_WITHDRAWAL_MICRO:
        await callback.answer(f"Мин. 1.00 USDT. У тебя: {fmt(fresh['balance'])}", show_alert=True)
        return
    await state.set_state(WithdrawState.amount)
    await callback.message.answer(
        f"📤 Доступно: <b>{fmt(fresh['balance'])} USDT</b>\nВведи сумму (мин. 1.00):",
    )
    await callback.answer()


@router.message(WithdrawState.amount)
async def withdraw_amount(message: Message, state: FSMContext, user: dict):
    if not message.text:
        await message.answer("Введи сумму числом.")
        return
    try:
        amount_usdt = float(message.text.replace(",", ".").strip())
        if amount_usdt < 1.0:
            await message.answer("Минимум 1.00 USDT.")
            return
        amount_micro = to_micro(amount_usdt)
    except ValueError:
        await message.answer("Некорректная сумма.")
        return

    fresh = await UserService.get_by_id(user["id"])
    if amount_micro > fresh["balance"]:
        await message.answer(f"Недостаточно. Доступно: {fmt(fresh['balance'])} USDT")
        return

    await state.update_data(amount_micro=amount_micro)
    await state.set_state(WithdrawState.wallet)
    await message.answer(
        "Адрес для вывода:\n"
        "• TRC20: <code>T...</code> (34 символа)\n"
        "• Telegram ID: 5–12 цифр"
    )


@router.message(WithdrawState.wallet)
async def withdraw_wallet(message: Message, state: FSMContext, user: dict, bot: Bot):
    if not message.text:
        await message.answer("Введи адрес текстом.")
        return

    wallet_addr = message.text.strip()
    if not _validate_wallet(wallet_addr):
        await message.answer("❌ Некорректный адрес. TRC20 (T + 33 символа) или Telegram ID (цифры).")
        return

    data = await state.get_data()
    amount_micro = data.get("amount_micro")
    if not amount_micro:
        await state.clear()
        await message.answer("Сессия устарела. Начни заново.")
        return

    # Cooldown: нельзя выводить первые 24ч после первой сделки
    fresh_check = await UserService.get_by_id(user["id"])
    if fresh_check.get("first_deal_at"):
        from datetime import datetime, timezone, timedelta
        try:
            first = datetime.fromisoformat(fresh_check["first_deal_at"])
            if first.tzinfo is None:
                first = first.replace(tzinfo=timezone.utc)
            cooldown_end = first + timedelta(hours=24)
            now = datetime.now(timezone.utc)
            if now < cooldown_end:
                await state.clear()
                lang = user.get("lang", "en")
                remaining = int((cooldown_end - now).total_seconds() / 3600) + 1
                await message.answer(
                    f"⏳ Withdrawal locked for {remaining}h after your first deal (anti-fraud)."
                    if lang == "en" else
                    f"⏳ Вывод заблокирован на {remaining}ч после первой сделки (защита от мошенничества)."
                )
                return
        except Exception:
            pass

    # Атомарно: списываем баланс + создаём заявку в одной транзакции
    try:
        async with transaction() as db:
            cur = await db.execute(
                "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?",
                (amount_micro, user["id"], amount_micro),
            )
            if cur.rowcount == 0:
                raise _InsufficientFunds()
            await db.execute(
                "INSERT INTO withdrawals (user_id, amount, wallet) VALUES (?, ?, ?)",
                (user["id"], amount_micro, wallet_addr),
            )
    except _InsufficientFunds:
        await state.clear()
        await message.answer("Недостаточно средств. Начни заново.")
        return

    # Получаем withdrawal_id
    db2 = await get_db()
    async with db2.execute(
        "SELECT id FROM withdrawals WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user["id"],),
    ) as cur:
        row = await cur.fetchone()
    withdrawal_id = row["id"]

    await OrderService.log_transaction(
        user_id=user["id"], tx_type="withdrawal",
        amount_micro=-amount_micro, comment=f"Withdrawal #{withdrawal_id}",
    )
    await state.clear()

    for admin_id in settings.get_admin_ids():
        try:
            await bot.send_message(
                admin_id,
                f"💸 <b>Вывод #{withdrawal_id}</b>\n"
                f"<code>{escape(user['ghost_id'])}</code> | {fmt(amount_micro)} USDT\n"
                f"Адрес: <code>{escape(wallet_addr)}</code>",
            )
        except Exception:
            pass

    await message.answer(
        f"✅ Заявка на вывод <b>{fmt(amount_micro)} USDT</b> создана. Обработка до 24ч.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "tx_history")
async def tx_history(callback: CallbackQuery, user: dict):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT 15",
        (user["id"],),
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        await callback.answer("Транзакций нет.", show_alert=True)
        return

    labels = {
        "escrow_in": "🔒 Эскроу", "escrow_release": "📤 Выход",
        "fee": "💸 Комиссия", "referral": "👥 Реферал",
        "refund": "↩️ Возврат", "withdrawal": "📤 Вывод",
    }
    lines = ["📊 <b>Транзакции</b>\n"]
    for tx in rows:
        sign = "+" if tx["amount"] >= 0 else "−"
        lines.append(
            f"{labels.get(tx['type'], tx['type'])}: "
            f"<b>{sign}{fmt(abs(tx['amount']))} USDT</b> "
            f"<i>{tx['created_at'][:16]}</i>"
        )
    await callback.message.answer("\n".join(lines))
    await callback.answer()


class _InsufficientFunds(Exception):
    pass
