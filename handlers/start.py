from html import escape
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from services.user_service import UserService
from services.review_service import ReviewService
from .keyboards import main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user: dict):
    args = message.text.split(maxsplit=1)
    # Реферальный аргумент учитывается только при первой регистрации (внутри middleware)
    _ = args  # noqa
    summary = await ReviewService.get_user_summary(user["id"])
    rating_line = (
        f"\nТвой рейтинг: ⭐ {summary['avg']:.1f} ({summary['count']} отзывов)"
        if summary["count"] > 0 else ""
    )
    await message.answer(
        f"🕶 <b>Anonex</b>\n\n"
        f"Анонимная P2P-биржа.\n"
        f"Твой ID: <code>{escape(user['ghost_id'])}</code>{rating_line}\n\n"
        f"Никакой регистрации. Никаких имён.\n"
        f"Только ты, продавец и крипта.\n\n"
        f"Меню ниже 👇",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Как работает Anonex</b>\n\n"
        "1. <b>🛒 Маркет</b> → выбери товар → оплати в USDT через CryptoBot\n"
        "2. <b>Эскроу</b> → деньги заморожены до подтверждения\n"
        "3. Продавец передаёт товар прямо в боте\n"
        "4. Подтверждаешь получение → деньги идут продавцу\n"
        "5. Молчишь 48ч → авто-подтверждение\n"
        "6. Проблема → открой спор, разберём вручную\n"
        "7. После сделки оставь ⭐ отзыв продавцу\n\n"
        "💰 Комиссия: 10% | 👥 Рефералы: 50% от комиссии навсегда\n"
        "⏳ Вывод: через 7 дней после подтверждения\n"
        "🕒 Срок объявлений: 30 дней"
    )


@router.message(F.text == "👥 Реферальная")
async def referral_info(message: Message, user: dict):
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user['ghost_id']}"
    ref_count = await UserService.count_referrals(user["id"])
    await message.answer(
        f"👥 <b>Реферальная программа Anonex</b>\n\n"
        f"50% от комиссии платформы с каждой сделки приглашённого — навсегда.\n\n"
        f"Твоя ссылка:\n<code>{escape(ref_link)}</code>\n\n"
        f"Приглашено: <b>{ref_count}</b> чел.",
    )
