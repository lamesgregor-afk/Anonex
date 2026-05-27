import logging
from html import escape
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from database.db import fmt
from services.admin_service import AdminService
from services.user_service import UserService
from services.order_service import OrderService
from services.crypto_service import CryptoService
from config import settings
from .keyboards import admin_main_keyboard, dispute_resolve_keyboard, withdrawal_keyboard

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user: dict) -> bool:
    return user["tg_id"] in settings.admin_ids


# ─── Панель ──────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def admin_panel(message: Message, user: dict):
    if not is_admin(user):
        return
    s = await AdminService.get_stats()
    await message.answer(
        f"🔧 <b>Админ-панель</b>\n\n"
        f"👤 Юзеров: {s['total_users']} | 📋 Листингов: {s['active_listings']}\n"
        f"📦 Заказов: {s['total_orders']} | 💰 Оборот: {fmt(s['total_volume_micro'])} USDT\n"
        f"💸 Комиссии: {fmt(s['platform_fees_micro'])} USDT\n"
        f"⚠️ Споров: {s['open_disputes']} | 📤 Выводов: {s['pending_withdrawals']}",
        reply_markup=admin_main_keyboard(),
    )


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, user: dict):
    if not is_admin(user):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    s = await AdminService.get_stats()
    await callback.message.edit_text(
        f"📈 <b>Статистика</b>\n\n"
        f"👤 {s['total_users']} | 📋 {s['active_listings']} | 📦 {s['total_orders']}\n"
        f"💰 Оборот: <b>{fmt(s['total_volume_micro'])} USDT</b>\n"
        f"💸 Комиссии: <b>{fmt(s['platform_fees_micro'])} USDT</b>\n"
        f"⚠️ {s['open_disputes']} споров | 📤 {s['pending_withdrawals']} выводов",
        reply_markup=admin_main_keyboard(),
    )
    await callback.answer()


# ─── Споры ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:disputes")
async def admin_disputes(callback: CallbackQuery, user: dict):
    if not is_admin(user):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    disputes = await AdminService.get_open_disputes()
    if not disputes:
        await callback.answer("Споров нет 🎉", show_alert=True)
        return
    for d in disputes[:5]:
        await callback.message.answer(
            f"⚠️ <b>Спор #{d['id']}</b> → Заказ #{d['order_id']}\n"
            f"👤 {escape(d['buyer_ghost'])} vs {escape(d['seller_ghost'])}\n"
            f"💰 {fmt(d['amount'])} USDT\n"
            f"Причина: {escape(d['reason'][:300])}",
            reply_markup=dispute_resolve_keyboard(d["id"]),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("resolve_buyer:"))
async def resolve_for_buyer(callback: CallbackQuery, user: dict, bot: Bot):
    if not is_admin(user):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    dispute_id = int(callback.data.split(":")[1])
    dispute = await AdminService.resolve_dispute(
        dispute_id, "resolved_buyer", user["id"], "Возврат покупателю"
    )
    if not dispute:
        await callback.answer("Уже решён.", show_alert=True)
        return

    order = await OrderService.get_by_id(dispute["order_id"])
    if order:
        buyer = await UserService.get_by_id(order["buyer_id"])
        if buyer:
            await UserService.add_balance(buyer["id"], order["amount"])
            await OrderService.log_transaction(
                user_id=buyer["id"], tx_type="refund",
                amount_micro=order["amount"], order_id=order["id"],
                comment=f"Refund dispute #{dispute_id}",
            )
            try:
                await bot.send_message(buyer["tg_id"],
                    f"↩️ Спор #{dispute_id} решён в твою пользу. +{fmt(order['amount'])} USDT")
            except Exception:
                pass
        seller = await UserService.get_by_id(order["seller_id"])
        if seller:
            try:
                await bot.send_message(seller["tg_id"],
                    f"⚠️ Спор #{dispute_id} — возврат покупателю.")
            except Exception:
                pass

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(f"✅ Спор #{dispute_id} — возврат покупателю.")
    await callback.answer()


@router.callback_query(F.data.startswith("resolve_seller:"))
async def resolve_for_seller(callback: CallbackQuery, user: dict, bot: Bot):
    if not is_admin(user):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    dispute_id = int(callback.data.split(":")[1])
    dispute = await AdminService.resolve_dispute(
        dispute_id, "resolved_seller", user["id"], "Выплата продавцу"
    )
    if not dispute:
        await callback.answer("Уже решён.", show_alert=True)
        return

    # AdminService уже выставил status='confirmed' + payout_available_at
    order = await OrderService.get_by_id(dispute["order_id"])
    if order:
        from handlers.orders import release_funds
        await release_funds(order, bot)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(f"✅ Спор #{dispute_id} — выплата продавцу (hold 7д).")
    await callback.answer()


# ─── Выводы ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:withdrawals")
async def admin_withdrawals(callback: CallbackQuery, user: dict):
    if not is_admin(user):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    wds = await AdminService.get_pending_withdrawals()
    if not wds:
        await callback.answer("Выводов нет.", show_alert=True)
        return
    for w in wds[:5]:
        await callback.message.answer(
            f"💸 <b>Вывод #{w['id']}</b>\n"
            f"<code>{escape(w['ghost_id'])}</code> | <b>{fmt(w['amount'])} USDT</b>\n"
            f"Адрес: <code>{escape(w['wallet'])}</code>",
            reply_markup=withdrawal_keyboard(w["id"]),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("w_approve:"))
async def approve_withdrawal(callback: CallbackQuery, user: dict, bot: Bot):
    if not is_admin(user):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    withdrawal_id = int(callback.data.split(":")[1])

    # Атомарно: pending → processing (защита от двойного клика)
    claimed = await AdminService.claim_withdrawal_for_processing(withdrawal_id)
    if not claimed:
        await callback.answer("Уже обработано.", show_alert=True)
        return

    w = await AdminService.get_withdrawal(withdrawal_id)
    if not w:
        await callback.answer("Не найдено.", show_alert=True)
        return

    # Пытаемся перевести через CryptoBot
    success = await CryptoService.transfer(
        tg_user_id=w["tg_id"],
        amount_micro=w["amount"],
        withdrawal_id=withdrawal_id,
    )

    if success:
        await AdminService.finalize_withdrawal(withdrawal_id, "done", "Transferred via CryptoBot")
        try:
            await bot.send_message(w["tg_id"],
                f"✅ Вывод #{withdrawal_id}: {fmt(w['amount'])} USDT отправлен.")
        except Exception:
            pass
        await callback.message.answer(f"✅ Вывод #{withdrawal_id} — переведено.")
    else:
        # Возвращаем деньги и ставим rejected
        await UserService.add_balance(w["user_id"], w["amount"])
        await AdminService.finalize_withdrawal(withdrawal_id, "rejected", "CryptoBot transfer failed")
        try:
            await bot.send_message(w["tg_id"],
                f"❌ Вывод #{withdrawal_id} не удался. {fmt(w['amount'])} USDT возвращены на баланс.")
        except Exception:
            pass
        await callback.message.answer(f"❌ Вывод #{withdrawal_id} — ошибка, возврат на баланс.")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("w_reject:"))
async def reject_withdrawal(callback: CallbackQuery, user: dict, bot: Bot):
    if not is_admin(user):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    withdrawal_id = int(callback.data.split(":")[1])
    w = await AdminService.get_withdrawal(withdrawal_id)
    if not w or w["status"] != "pending":
        await callback.answer("Уже обработано.", show_alert=True)
        return

    ok = await AdminService.reject_pending_withdrawal(withdrawal_id, "Admin rejected")
    if not ok:
        await callback.answer("Ошибка.", show_alert=True)
        return

    await UserService.add_balance(w["user_id"], w["amount"])
    try:
        await bot.send_message(w["tg_id"],
            f"❌ Вывод #{withdrawal_id} отклонён. {fmt(w['amount'])} USDT возвращены.")
    except Exception:
        pass

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(f"❌ Вывод #{withdrawal_id} отклонён, средства возвращены.")
    await callback.answer()


# ─── Транзакции ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:transactions")
async def admin_transactions(callback: CallbackQuery, user: dict):
    if not is_admin(user):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    txs = await AdminService.get_recent_transactions(20)
    if not txs:
        await callback.answer("Нет.", show_alert=True)
        return
    lines = ["📊 <b>Транзакции (20)</b>\n"]
    for tx in txs:
        sign = "+" if tx["amount"] >= 0 else "−"
        lines.append(
            f"<code>{escape(tx['ghost_id'])}</code> {escape(tx['type'])} "
            f"{sign}{fmt(abs(tx['amount']))} {tx['created_at'][:16]}"
        )
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3990] + "\n..."
    await callback.message.answer(text)
    await callback.answer()


# ─── Бан ──────────────────────────────────────────────────────────────────────

@router.message(Command("ban"))
async def ban_cmd(message: Message, user: dict):
    if not is_admin(user):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("/ban ghost_xxxxxxx")
        return
    ghost_id = args[1].strip()
    tg_id = await AdminService.ban_user(ghost_id)
    await message.answer(f"{'✅ Забанен' if tg_id else '❌ Не найден'}: {escape(ghost_id)}")


@router.message(Command("unban"))
async def unban_cmd(message: Message, user: dict):
    if not is_admin(user):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("/unban ghost_xxxxxxx")
        return
    ghost_id = args[1].strip()
    ok = await AdminService.unban_user(ghost_id)
    await message.answer(f"{'✅ Разбанен' if ok else '❌ Не найден'}: {escape(ghost_id)}")
