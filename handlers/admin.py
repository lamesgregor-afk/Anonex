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


# ─── Управление объявлениями ─────────────────────────────────────────────────

@router.callback_query(F.data == "admin:listings")
async def admin_listings(callback: CallbackQuery, user: dict):
    if not is_admin(user):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    from services.listing_service import ListingService, CATEGORY_EMOJI
    from database.db import get_db as _get
    from .keyboards import admin_listing_card

    db = await _get()
    async with db.execute(
        """SELECT l.*, u.ghost_id as seller_ghost
           FROM listings l JOIN users u ON l.seller_id = u.id
           WHERE l.is_active = 1
           ORDER BY l.created_at DESC LIMIT 10"""
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        await callback.answer("Активных объявлений нет.", show_alert=True)
        return

    await callback.message.answer("📋 <b>Активные объявления (10)</b>")
    for lst in rows:
        emoji = CATEGORY_EMOJI.get(lst["category"], "🔖")
        await callback.message.answer(
            f"{emoji} <b>{escape(lst['title'])}</b>\n"
            f"ID: <code>{lst['id']}</code> | {fmt(lst['price'])} USDT\n"
            f"👤 <code>{escape(lst['seller_ghost'])}</code> | {lst['created_at'][:10]}\n"
            f"{escape(lst['description'][:200])}",
            reply_markup=admin_listing_card(lst["id"]),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_del:"))
async def admin_delete_listing(callback: CallbackQuery, user: dict, bot: Bot):
    if not is_admin(user):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    from services.listing_service import ListingService

    listing_id = int(callback.data.split(":")[1])
    listing = await ListingService.get_by_id(listing_id)
    if not listing:
        await callback.answer("Не найдено.", show_alert=True)
        return

    ok = await ListingService.admin_deactivate(listing_id)
    if not ok:
        await callback.answer("Не удалось.", show_alert=True)
        return

    # Уведомляем продавца
    seller = await UserService.get_by_id(listing["seller_id"])
    if seller:
        try:
            await bot.send_message(
                seller["tg_id"],
                f"🛑 Объявление «{escape(listing['title'])}» снято администратором.",
            )
        except Exception:
            pass

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("✅ Удалено.", show_alert=True)


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



# ─── Управление категориями ──────────────────────────────────────────────────

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.category_service import CategoryService


class AdminCatState(StatesGroup):
    new_root_name = State()
    new_root_emoji = State()
    new_sub_name = State()
    rename = State()
    approve_name = State()
    approve_emoji = State()


def _root_admin_kb():
    """Список root-категорий с кнопками управления."""
    return None  # рендерится отдельно


@router.callback_query(F.data == "admin:categories")
async def admin_categories(callback: CallbackQuery, user: dict):
    if not is_admin(user):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    roots = await CategoryService.get_roots()
    kb = InlineKeyboardBuilder()
    for c in roots:
        cnt = await CategoryService.count_listings(c["id"])
        kb.button(
            text=f"{c['emoji']} {c['name']} ({cnt})",
            callback_data=f"adm_cat:open:{c['id']}",
        )
    kb.adjust(2)
    kb.row()
    kb.button(text="➕ Новая корневая", callback_data="adm_cat:new_root")
    await callback.message.answer(
        "📂 <b>Категории</b>\nВыбери для управления или создай новую:",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_cat:open:"))
async def admin_cat_open(callback: CallbackQuery, user: dict):
    if not is_admin(user):
        return
    cat_id = int(callback.data.split(":")[2])
    cat = await CategoryService.get_by_id(cat_id)
    if not cat:
        await callback.answer("Не найдено.", show_alert=True)
        return

    children = await CategoryService.get_children(cat_id) if cat["parent_id"] is None else []

    kb = InlineKeyboardBuilder()
    if cat["parent_id"] is None:
        # Root: показываем дочерние + действия
        for ch in children:
            kb.button(text=f"{ch['emoji']} {ch['name']}", callback_data=f"adm_cat:open:{ch['id']}")
        kb.adjust(2)
        kb.row()
        kb.button(text="➕ Подкатегория", callback_data=f"adm_cat:new_sub:{cat_id}")
    kb.row()
    kb.button(text="✏️ Переименовать", callback_data=f"adm_cat:rename:{cat_id}")
    kb.button(text="🛑 Деактивировать", callback_data=f"adm_cat:disable:{cat_id}")
    kb.adjust(2)

    path = await CategoryService.get_path(cat_id)
    label = " → ".join(f"{p['emoji']} {p['name']}" for p in path)
    cnt = await CategoryService.count_listings(cat_id)

    await callback.message.answer(
        f"📂 {escape(label)}\n"
        f"ID: <code>{cat_id}</code> | Активных листингов: {cnt}\n"
        + (f"Подкатегорий: {len(children)}\n" if cat["parent_id"] is None else ""),
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_cat:new_root")
async def admin_cat_new_root(callback: CallbackQuery, state: FSMContext, user: dict):
    if not is_admin(user):
        return
    await state.set_state(AdminCatState.new_root_name)
    await callback.message.answer("Название новой корневой категории:")
    await callback.answer()


@router.message(AdminCatState.new_root_name)
async def admin_cat_new_root_name(message: Message, state: FSMContext, user: dict):
    if not is_admin(user) or not message.text:
        return
    name = message.text.strip()[:60]
    if not name:
        await message.answer("Пустое.")
        return
    await state.update_data(name=name)
    await state.set_state(AdminCatState.new_root_emoji)
    await message.answer("Эмодзи (1 символ, например 🎮):")


@router.message(AdminCatState.new_root_emoji)
async def admin_cat_new_root_emoji(message: Message, state: FSMContext, user: dict):
    if not is_admin(user) or not message.text:
        return
    emoji = message.text.strip()[:8] or "🔖"
    data = await state.get_data()
    cat = await CategoryService.create(name=data["name"], emoji=emoji, parent_id=None)
    await state.clear()
    await message.answer(f"✅ Создана: {cat['emoji']} {escape(cat['name'])} (ID {cat['id']})")


@router.callback_query(F.data.startswith("adm_cat:new_sub:"))
async def admin_cat_new_sub(callback: CallbackQuery, state: FSMContext, user: dict):
    if not is_admin(user):
        return
    parent_id = int(callback.data.split(":")[2])
    await state.update_data(parent_id=parent_id)
    await state.set_state(AdminCatState.new_sub_name)
    await callback.message.answer("Название подкатегории (можно с эмодзи в начале, напр. «🎯 Valorant»):")
    await callback.answer()


@router.message(AdminCatState.new_sub_name)
async def admin_cat_new_sub_name(message: Message, state: FSMContext, user: dict):
    if not is_admin(user) or not message.text:
        return
    raw = message.text.strip()
    # Пробуем выделить эмодзи в начале
    parts = raw.split(maxsplit=1)
    emoji = "🔖"
    name = raw
    if len(parts) == 2 and len(parts[0]) <= 4:
        emoji = parts[0]
        name = parts[1]

    data = await state.get_data()
    cat = await CategoryService.create(name=name[:60], emoji=emoji, parent_id=data["parent_id"])
    await state.clear()
    await message.answer(f"✅ Подкатегория: {cat['emoji']} {escape(cat['name'])} (ID {cat['id']})")


@router.callback_query(F.data.startswith("adm_cat:rename:"))
async def admin_cat_rename_start(callback: CallbackQuery, state: FSMContext, user: dict):
    if not is_admin(user):
        return
    cat_id = int(callback.data.split(":")[2])
    await state.update_data(rename_id=cat_id)
    await state.set_state(AdminCatState.rename)
    await callback.message.answer(
        "Введи новое название (можно «🎮 Имя» с эмодзи в начале):"
    )
    await callback.answer()


@router.message(AdminCatState.rename)
async def admin_cat_rename_save(message: Message, state: FSMContext, user: dict):
    if not is_admin(user) or not message.text:
        return
    data = await state.get_data()
    cat_id = data.get("rename_id")
    raw = message.text.strip()
    parts = raw.split(maxsplit=1)
    emoji = None
    name = raw
    if len(parts) == 2 and len(parts[0]) <= 4:
        emoji = parts[0]
        name = parts[1]
    ok = await CategoryService.rename(cat_id, name[:60], emoji)
    await state.clear()
    await message.answer("✅ Переименовано." if ok else "❌ Не удалось.")


@router.callback_query(F.data.startswith("adm_cat:disable:"))
async def admin_cat_disable(callback: CallbackQuery, user: dict):
    if not is_admin(user):
        return
    cat_id = int(callback.data.split(":")[2])
    ok = await CategoryService.deactivate(cat_id)
    await callback.answer("✅ Деактивирована" if ok else "❌", show_alert=True)


# ─── Заявки на категории ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:suggestions")
async def admin_suggestions(callback: CallbackQuery, user: dict):
    if not is_admin(user):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    items = await CategoryService.get_pending_suggestions(limit=10)
    if not items:
        await callback.answer("Заявок нет.", show_alert=True)
        return
    for s in items:
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Принять", callback_data=f"sug:approve:{s['id']}")
        kb.button(text="❌ Отклонить", callback_data=f"sug:reject:{s['id']}")
        kb.adjust(2)
        await callback.message.answer(
            f"💡 <b>Заявка #{s['id']}</b>\n"
            f"От: <code>{escape(s['ghost_id'])}</code>\n"
            f"Название: «{escape(s['suggested'])}»\n"
            f"<i>{s['created_at'][:16]}</i>",
            reply_markup=kb.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("sug:approve:"))
async def admin_sug_approve(callback: CallbackQuery, state: FSMContext, user: dict):
    if not is_admin(user):
        return
    sug_id = int(callback.data.split(":")[2])
    sug = await CategoryService.get_suggestion(sug_id)
    if not sug or sug["status"] != "pending":
        await callback.answer("Уже обработана.", show_alert=True)
        return

    # Покажем root-категории чтобы выбрать куда добавить
    roots = await CategoryService.get_roots()
    kb = InlineKeyboardBuilder()
    for r in roots:
        kb.button(text=f"{r['emoji']} {r['name']}", callback_data=f"sug_to:{sug_id}:{r['id']}")
    kb.adjust(2)
    kb.row()
    kb.button(text="➕ Как корневую", callback_data=f"sug_to:{sug_id}:0")
    await callback.message.answer(
        f"Куда добавить «{escape(sug['suggested'])}»?",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sug_to:"))
async def admin_sug_place(callback: CallbackQuery, state: FSMContext, user: dict, bot: Bot):
    if not is_admin(user):
        return
    parts = callback.data.split(":")
    sug_id = int(parts[1])
    parent_id = int(parts[2])  # 0 = root
    sug = await CategoryService.get_suggestion(sug_id)
    if not sug or sug["status"] != "pending":
        await callback.answer("Уже обработана.", show_alert=True)
        return

    await state.update_data(sug_id=sug_id, parent_id=(parent_id or None))
    await state.set_state(AdminCatState.approve_name)
    await callback.message.answer(
        f"Заявка: «{escape(sug['suggested'])}»\n\n"
        f"Введи финальное название (можно с эмодзи в начале) "
        f"или просто <b>=</b> чтобы принять как есть:",
    )
    await callback.answer()


@router.message(AdminCatState.approve_name)
async def admin_sug_approve_save(message: Message, state: FSMContext, user: dict, bot: Bot):
    if not is_admin(user) or not message.text:
        return
    data = await state.get_data()
    sug_id = data["sug_id"]
    parent_id = data.get("parent_id")

    sug = await CategoryService.get_suggestion(sug_id)
    if not sug:
        await state.clear()
        await message.answer("Заявка пропала.")
        return

    raw = message.text.strip()
    if raw == "=":
        name = sug["suggested"]
        emoji = "🔖"
    else:
        parts = raw.split(maxsplit=1)
        if len(parts) == 2 and len(parts[0]) <= 4:
            emoji = parts[0]
            name = parts[1]
        else:
            emoji = "🔖"
            name = raw

    cat = await CategoryService.create(name=name[:60], emoji=emoji, parent_id=parent_id)
    await CategoryService.update_suggestion_status(sug_id, "approved", f"Created cat #{cat['id']}")
    await state.clear()

    # Уведомляем юзера
    try:
        await bot.send_message(
            sug["tg_id"],
            f"✅ Твоя заявка «{escape(sug['suggested'])}» одобрена!\n"
            f"Добавлена категория {cat['emoji']} {escape(cat['name'])}.",
        )
    except Exception:
        pass

    await message.answer(
        f"✅ Категория создана: {cat['emoji']} {escape(cat['name'])} (ID {cat['id']})"
    )


@router.callback_query(F.data.startswith("sug:reject:"))
async def admin_sug_reject(callback: CallbackQuery, user: dict, bot: Bot):
    if not is_admin(user):
        return
    sug_id = int(callback.data.split(":")[2])
    sug = await CategoryService.get_suggestion(sug_id)
    if not sug:
        await callback.answer("Не найдено.", show_alert=True)
        return
    ok = await CategoryService.update_suggestion_status(sug_id, "rejected", "Admin rejected")
    if not ok:
        await callback.answer("Уже обработана.", show_alert=True)
        return
    try:
        await bot.send_message(
            sug["tg_id"],
            f"❌ Заявка на категорию «{escape(sug['suggested'])}» отклонена.",
        )
    except Exception:
        pass
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("Отклонено.")
