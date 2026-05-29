"""
deal_chat.py — анонимный чат внутри сделки.

Флоу:
  1. После оплаты (status=paid) продавцу и покупателю показывается кнопка 💬 Chat
  2. Любой из них может написать — бот проксирует сообщение другой стороне
  3. Получатель видит роль отправителя (Buyer / Seller), но не его ID
  4. Кнопки ✅ Confirm / ⚠️ Dispute прямо в чате (у покупателя)
  5. Чат закрывается после confirmed/disputed/cancelled

FSM: DealChatState.writing — юзер в режиме чата по конкретному ордеру.
     Выход: /exit_chat или нажатие кнопки меню.
"""
import logging
from html import escape
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.order_service import OrderService
from services.user_service import UserService
from services.chat_service import ChatService
import i18n

logger = logging.getLogger(__name__)
router = Router()

_ACTIVE_STATUSES = ("paid", "delivered")
_CLOSED_STATUSES = ("confirmed", "paid_out", "cancelled", "refunded", "disputed")


class DealChatState(StatesGroup):
    writing = State()


def _chat_keyboard(order_id: int, role: str, lang: str = "en") -> "InlineKeyboardMarkup":
    """Клавиатура внутри чата. Покупателю — кнопки подтверждения и спора."""
    kb = InlineKeyboardBuilder()
    if role == "buyer":
        kb.button(
            text="✅ Confirm receipt" if lang == "en" else "✅ Подтвердить получение",
            callback_data=f"chat_confirm:{order_id}",
        )
        kb.button(
            text="⚠️ Open dispute" if lang == "en" else "⚠️ Открыть спор",
            callback_data=f"chat_dispute:{order_id}",
        )
        kb.adjust(1)
    kb.row()
    kb.button(
        text="🚪 Exit chat" if lang == "en" else "🚪 Выйти из чата",
        callback_data="chat_exit",
    )
    return kb.as_markup()


def _open_chat_keyboard(order_id: int, lang: str = "en") -> "InlineKeyboardMarkup":
    kb = InlineKeyboardBuilder()
    kb.button(
        text="💬 Open chat" if lang == "en" else "💬 Открыть чат",
        callback_data=f"open_chat:{order_id}",
    )
    return kb.as_markup()


# ─── Открыть чат ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("open_chat:"))
async def open_chat(callback: CallbackQuery, state: FSMContext, user: dict):
    order_id = int(callback.data.split(":")[1])
    order = await OrderService.get_by_id(order_id)

    if not order:
        await callback.answer("Order not found." if user.get("lang") == "en" else "Заказ не найден.", show_alert=True)
        return

    is_buyer = order["buyer_id"] == user["id"]
    is_seller = order["seller_id"] == user["id"]
    if not is_buyer and not is_seller:
        await callback.answer("No access." if user.get("lang") == "en" else "Нет доступа.", show_alert=True)
        return

    if order["status"] in _CLOSED_STATUSES:
        msg = "Chat closed." if user.get("lang") == "en" else "Чат закрыт."
        await callback.answer(msg, show_alert=True)
        return

    role = "buyer" if is_buyer else "seller"
    await ChatService.enable_chat(order_id)
    await state.set_state(DealChatState.writing)
    await state.update_data(order_id=order_id, role=role)

    lang = user.get("lang", "en")
    other_role = "Seller" if role == "buyer" else "Buyer"
    if lang == "ru":
        other_role = "Продавец" if role == "buyer" else "Покупатель"

    history = await ChatService.get_history(order_id, limit=20)

    header = (
        f"💬 <b>Deal chat #{order_id}</b>\n"
        f"You are: <b>{'Buyer' if role == 'buyer' else 'Seller'}</b>\n\n"
        if lang == "en" else
        f"💬 <b>Чат по сделке #{order_id}</b>\n"
        f"Ты: <b>{'Покупатель' if role == 'buyer' else 'Продавец'}</b>\n\n"
    )

    if history:
        lines = []
        for msg in history[-10:]:
            r = "🛒 Buyer" if msg["role"] == "buyer" else "📦 Seller"
            if lang == "ru":
                r = "🛒 Покупатель" if msg["role"] == "buyer" else "📦 Продавец"
            if msg["text"]:
                lines.append(f"<b>{r}:</b> {escape(msg['text'])}")
            else:
                lines.append(f"<b>{r}:</b> [file]")
        header += "\n".join(lines) + "\n\n"

    hint = (
        "Type your message. Use /exit_chat to leave.\n"
        if lang == "en" else
        "Напиши сообщение. /exit_chat чтобы выйти.\n"
    )

    await callback.message.answer(
        header + hint,
        reply_markup=_chat_keyboard(order_id, role, lang),
    )
    await callback.answer()


# ─── Выход из чата ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "chat_exit")
async def chat_exit_cb(callback: CallbackQuery, state: FSMContext, user: dict):
    await state.clear()
    lang = user.get("lang", "en")
    await callback.message.answer(
        "Chat closed." if lang == "en" else "Чат закрыт.",
    )
    await callback.answer()


@router.message(DealChatState.writing, F.text == "/exit_chat")
async def chat_exit_cmd(message: Message, state: FSMContext, user: dict):
    await state.clear()
    lang = user.get("lang", "en")
    await message.answer("Chat closed." if lang == "en" else "Чат закрыт.")


# ─── Сообщения в чате ────────────────────────────────────────────────────────

@router.message(DealChatState.writing)
async def chat_message(message: Message, state: FSMContext, user: dict, bot: Bot):
    data = await state.get_data()
    order_id = data.get("order_id")
    role = data.get("role")
    if not order_id or not role:
        await state.clear()
        return

    order = await OrderService.get_by_id(order_id)
    if not order or order["status"] in _CLOSED_STATUSES:
        await state.clear()
        lang = user.get("lang", "en")
        await message.answer(
            "Chat closed — deal is no longer active." if lang == "en"
            else "Чат закрыт — сделка завершена."
        )
        return

    lang = user.get("lang", "en")

    # Определяем получателя
    other_id = order["buyer_id"] if role == "seller" else order["seller_id"]
    other_user = await UserService.get_by_id(other_id)
    if not other_user:
        return

    # Сохраняем сообщение
    text = message.text
    file_id = None
    file_type = None
    if message.document:
        file_id = message.document.file_id
        file_type = "document"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.audio:
        file_id = message.audio.file_id
        file_type = "audio"

    await ChatService.save_message(
        order_id=order_id,
        sender_id=user["id"],
        role=role,
        text=text,
        file_id=file_id,
        file_type=file_type,
    )

    # Метка отправителя для получателя
    sender_label = (
        ("🛒 Buyer" if role == "buyer" else "📦 Seller")
        if lang == "en" else
        ("🛒 Покупатель" if role == "buyer" else "📦 Продавец")
    )

    other_role = "seller" if role == "buyer" else "buyer"
    other_lang = other_user.get("lang", "en")
    other_sender_label = (
        ("🛒 Buyer" if role == "buyer" else "📦 Seller")
        if other_lang == "en" else
        ("🛒 Покупатель" if role == "buyer" else "📦 Продавец")
    )

    # Отправляем получателю
    try:
        prefix = f"💬 <b>Deal #{order_id} — {other_sender_label}:</b>\n"
        kb = _chat_keyboard(order_id, other_role, other_lang)

        if file_id and file_type:
            await message.copy_to(other_user["tg_id"])
            await bot.send_message(
                other_user["tg_id"],
                prefix + ("[file]" if not text else escape(text)),
                reply_markup=kb,
            )
        else:
            await bot.send_message(
                other_user["tg_id"],
                prefix + escape(text or ""),
                reply_markup=kb,
            )
    except Exception:
        logger.warning("[chat] Can't deliver to tg_id=%d", other_user["tg_id"])

    # Подтверждение отправителю
    sent_label = "✉️ Sent" if lang == "en" else "✉️ Отправлено"
    await message.answer(sent_label, reply_markup=_chat_keyboard(order_id, role, lang))


# ─── Confirm / Dispute прямо из чата ─────────────────────────────────────────

@router.callback_query(F.data.startswith("chat_confirm:"))
async def chat_confirm(callback: CallbackQuery, state: FSMContext, user: dict, bot: Bot):
    order_id = int(callback.data.split(":")[1])
    order = await OrderService.get_by_id(order_id)
    if not order or order["buyer_id"] != user["id"]:
        await callback.answer("No access." if user.get("lang") == "en" else "Нет доступа.", show_alert=True)
        return

    changed = await OrderService.try_mark_confirmed(order_id)
    if not changed:
        await callback.answer("Already processed." if user.get("lang") == "en" else "Уже обработано.", show_alert=True)
        return

    await state.clear()
    order = await OrderService.get_by_id(order_id)

    from handlers.orders import release_funds
    await release_funds(order, bot)

    lang = user.get("lang", "en")
    await callback.message.answer(
        f"✅ Order #{order_id} confirmed!" if lang == "en"
        else f"✅ Заказ #{order_id} подтверждён!"
    )
    await callback.answer()

    from handlers.reviews import request_review
    await request_review(bot, user["tg_id"], order_id)


@router.callback_query(F.data.startswith("chat_dispute:"))
async def chat_dispute_start(callback: CallbackQuery, state: FSMContext, user: dict):
    order_id = int(callback.data.split(":")[1])
    order = await OrderService.get_by_id(order_id)
    if not order or order["buyer_id"] != user["id"]:
        await callback.answer("No access." if user.get("lang") == "en" else "Нет доступа.", show_alert=True)
        return
    if order["status"] not in ("paid", "delivered"):
        await callback.answer("Can't open dispute now." if user.get("lang") == "en" else "Нельзя открыть спор.", show_alert=True)
        return

    # Переключаем FSM на ввод причины спора
    from handlers.orders import DisputeState
    await state.set_state(DisputeState.reason)
    await state.update_data(order_id=order_id)
    lang = user.get("lang", "en")
    await callback.message.answer(
        i18n.get(user, "dispute_prompt", id=order_id)
    )
    await callback.answer()
