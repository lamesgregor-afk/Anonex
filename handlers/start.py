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
    lang = user.get("lang", "en")
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="🛒 Market" if lang == "en" else "🛒 Маркет"),
        KeyboardButton(text="🔍 Search" if lang == "en" else "🔍 Поиск"),
    )
    kb.row(
        KeyboardButton(text="➕ Sell" if lang == "en" else "➕ Продать"),
        KeyboardButton(text="📦 My Purchases" if lang == "en" else "📦 Мои покупки"),
    )
    kb.row(
        KeyboardButton(text="📋 My Listings" if lang == "en" else "📋 Мои товары"),
        KeyboardButton(text="💼 Wallet" if lang == "en" else "💼 Кошелёк"),
    )
    kb.row(
        KeyboardButton(text="👥 Referral" if lang == "en" else "👥 Реферальная"),
        KeyboardButton(text="🔔 Subscriptions" if lang == "en" else "🔔 Подписки"),
    )
    kb.row(KeyboardButton(text="🌐 Interface language" if lang == "en" else "🌐 Язык интерфейса"))
    return kb.as_markup(resize_keyboard=True)


def lang_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🇬🇧 English", callback_data="setlang:en")
    kb.button(text="🇷🇺 Русский", callback_data="setlang:ru")
    kb.adjust(2)
    return kb.as_markup()


_ALL_MENU_TEXTS = {
    "🛒 Market", "🛒 Маркет",
    "🔍 Search", "🔍 Поиск",
    "➕ Sell", "➕ Продать",
    "📦 My Purchases", "📦 Мои покупки",
    "📋 My Listings", "📋 Мои товары",
    "💼 Wallet", "💼 Кошелёк",
    "👥 Referral", "👥 Реферальная",
    "🔔 Subscriptions", "🔔 Подписки",
    "🌐 Interface language", "🌐 Язык интерфейса",
}


def get_all_menu_texts():
    return _ALL_MENU_TEXTS


@router.message(CommandStart())
async def cmd_start(message: Message, user: dict, state: FSMContext):
    await state.clear()
    summary = await ReviewService.get_user_summary(user["id"])
    rating_line = (
        i18n.get(user, "start_rating", avg=summary["avg"], count=summary["count"])
        if summary["count"] > 0 else ""
    )
    await message.answer(
        i18n.get(user, "start_welcome",
                 ghost_id=escape(user["ghost_id"]),
                 rating_line=rating_line),
        reply_markup=main_menu(user),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, user: dict):
    await message.answer(i18n.get(user, "help_text"))


@router.message(F.text.in_({"🌐 Interface language", "🌐 Язык интерфейса"}))
async def choose_language(message: Message, user: dict):
    await message.answer(
        "🌐 Choose interface language / Выбери язык интерфейса:",
        reply_markup=lang_keyboard(),
    )


@router.callback_query(F.data.startswith("setlang:"))
async def set_language(callback: CallbackQuery, user: dict):
    lang = callback.data.split(":")[1]
    if lang not in ("en", "ru"):
        await callback.answer()
        return
    await UserService.set_lang(user["id"], lang)
    user["lang"] = lang
    await callback.message.answer(
        i18n.get(user, "lang_changed"),
        reply_markup=main_menu(user),
    )
    await callback.answer()


@router.message(F.text.in_({"👥 Referral", "👥 Реферальная"}))
async def referral_info(message: Message, user: dict):
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user['ghost_id']}"
    ref_count = await UserService.count_referrals(user["id"])
    await message.answer(
        i18n.get(user, "referral_info", link=escape(ref_link), count=ref_count)
    )
