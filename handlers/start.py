from html import escape
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from services.user_service import UserService
from services.review_service import ReviewService
import i18n

router = Router()


def main_menu(user: dict) -> ReplyKeyboardMarkup:
    """Меню на языке пользователя."""
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text=i18n.get(user, "btn_market")),
        KeyboardButton(text=i18n.get(user, "btn_sell")),
    )
    kb.row(
        KeyboardButton(text=i18n.get(user, "btn_purchases")),
        KeyboardButton(text=i18n.get(user, "btn_listings")),
    )
    kb.row(
        KeyboardButton(text=i18n.get(user, "btn_wallet")),
        KeyboardButton(text=i18n.get(user, "btn_referral")),
    )
    kb.row(KeyboardButton(text=i18n.get(user, "btn_language")))
    return kb.as_markup(resize_keyboard=True)


def lang_keyboard() -> "InlineKeyboardMarkup":
    kb = InlineKeyboardBuilder()
    kb.button(text="🇬🇧 English", callback_data="setlang:en")
    kb.button(text="🇷🇺 Русский", callback_data="setlang:ru")
    kb.adjust(2)
    return kb.as_markup()


@router.message(CommandStart())
async def cmd_start(message: Message, user: dict, state: FSMContext):
    await state.clear()  # сбрасываем любой FSM при /start
    summary = await ReviewService.get_user_summary(user["id"])
    rating_line = (
        i18n.get(user, "start_rating", avg=summary["avg"], count=summary["count"])
        if summary["count"] > 0 else ""
    )
    await message.answer(
        i18n.get(user, "start_welcome", ghost_id=escape(user["ghost_id"]), rating_line=rating_line),
        reply_markup=main_menu(user),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, user: dict):
    await message.answer(i18n.get(user, "help_text"))


# ─── Язык ────────────────────────────────────────────────────────────────────

@router.message(lambda m: m.text in ("🌐 Language", "🌐 Язык"))
async def choose_language(message: Message, user: dict):
    await message.answer("🌐 Choose language / Выбери язык:", reply_markup=lang_keyboard())


@router.callback_query(F.data.startswith("setlang:"))
async def set_language(callback: CallbackQuery, user: dict):
    lang = callback.data.split(":")[1]
    if lang not in ("en", "ru"):
        await callback.answer()
        return
    await UserService.set_lang(user["id"], lang)
    # Обновляем user dict для текущего запроса
    user["lang"] = lang
    await callback.message.answer(
        i18n.get(user, "lang_changed"),
        reply_markup=main_menu(user),
    )
    await callback.answer()


# ─── Реферальная ─────────────────────────────────────────────────────────────

@router.message(lambda m: m.text in ("👥 Referral", "👥 Реферальная"))
async def referral_info(message: Message, user: dict):
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user['ghost_id']}"
    ref_count = await UserService.count_referrals(user["id"])
    await message.answer(
        i18n.get(user, "referral_info", link=escape(ref_link), count=ref_count)
    )
