"""
reviews.py — оценки и текстовые отзывы после завершения сделки.

Флоу:
  Покупатель подтвердил получение → бот шлёт клавиатуру со звёздами
  → выбирает 1-5 → бот предлагает написать текст (опционально)
  → текст или /skip → отзыв сохранён.
"""
import logging
from html import escape
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.review_service import ReviewService
from services.order_service import OrderService
from services.user_service import UserService
from .keyboards import review_keyboard, main_menu

logger = logging.getLogger(__name__)
router = Router()


class ReviewState(StatesGroup):
    text = State()


async def request_review(bot: Bot, buyer_tg_id: int, order_id: int):
    """Отправляет покупателю клавиатуру с оценками. Вызывается после confirm."""
    try:
        await bot.send_message(
            buyer_tg_id,
            f"⭐ <b>Оцени сделку #{order_id}</b>\n\n"
            f"Поставь продавцу оценку — это поможет другим покупателям.",
            reply_markup=review_keyboard(order_id),
        )
    except Exception:
        logger.warning("[reviews] Can't send review request to %d", buyer_tg_id)


@router.callback_query(F.data.startswith("rate:"))
async def rate_callback(callback: CallbackQuery, state: FSMContext, user: dict):
    parts = callback.data.split(":")
    order_id = int(parts[1])
    rating = int(parts[2])

    order = await OrderService.get_by_id(order_id)
    if not order or order["buyer_id"] != user["id"]:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    if order["status"] not in ("confirmed", "paid_out"):
        await callback.answer("Можно оценить только завершённую сделку.", show_alert=True)
        return

    # Уже есть отзыв?
    existing = await ReviewService.get_for_order(order_id)
    if existing:
        await callback.answer("Ты уже оставил отзыв на эту сделку.", show_alert=True)
        return

    if rating == 0:
        # Пропустить
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.answer("Понял, отзыв пропущен.")
        return

    if rating < 1 or rating > 5:
        await callback.answer("Некорректная оценка.", show_alert=True)
        return

    # Сохраняем оценку, спрашиваем текст
    await state.set_state(ReviewState.text)
    await state.update_data(order_id=order_id, rating=rating)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(
        f"Оценка: {'⭐' * rating}\n\n"
        f"Хочешь добавить текст? (до 500 символов)\n"
        f"Или напиши /skip чтобы оставить только звёзды.",
    )
    await callback.answer()


@router.message(ReviewState.text)
async def rate_text(message: Message, state: FSMContext, user: dict):
    data = await state.get_data()
    order_id = data.get("order_id")
    rating = data.get("rating")
    if not order_id or not rating:
        await state.clear()
        return

    text = None
    if message.text and message.text.strip().lower() not in ("/skip", "skip", "-"):
        text = message.text.strip()[:500]

    order = await OrderService.get_by_id(order_id)
    if not order or order["buyer_id"] != user["id"]:
        await state.clear()
        await message.answer("Что-то пошло не так.", reply_markup=main_menu())
        return

    review = await ReviewService.create(
        order_id=order_id,
        reviewer_id=user["id"],
        target_id=order["seller_id"],
        rating=rating,
        text=text,
    )
    await state.clear()

    if not review:
        await message.answer("Не удалось сохранить отзыв.", reply_markup=main_menu())
        return

    await message.answer(
        f"✅ Спасибо! Твой отзыв сохранён.\n\n{'⭐' * rating}"
        + (f"\n💬 {escape(text)}" if text else ""),
        reply_markup=main_menu(),
    )

    # Уведомляем продавца
    seller = await UserService.get_by_id(order["seller_id"])
    if seller:
        try:
            from aiogram import Bot
            bot: Bot = message.bot
            preview = f"\n💬 {escape(text)}" if text else ""
            await bot.send_message(
                seller["tg_id"],
                f"⭐ Новый отзыв по сделке #{order_id}: {'⭐' * rating}{preview}",
            )
        except Exception:
            pass
