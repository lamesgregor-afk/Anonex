from html import escape
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from services.user_service import UserService
from .keyboards import main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user: dict):
    # user уже создан middleware-ом при первом обращении
    # Если пришёл с реф-аргументом — пересоздавать не нужно,
    # middleware сделал get_or_create с referrer при регистрации
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and user.get("referrer_id") is None:
        # Пользователь уже существует без реферера — игнорируем попытку переписать
        pass

    await message.answer(
        f"👻 <b>GhostMarket</b>\n\n"
        f"Анонимный P2P-маркетплейс.\n"
        f"Твой ID: <code>{escape(user['ghost_id'])}</code>\n\n"
        f"Никакой регистрации. Никаких имён.\n"
        f"Только ты, продавец и крипта.\n\n"
        f"Используй меню ниже 👇",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Как это работает</b>\n\n"
        "1. <b>Покупка</b> → 🛒 Маркет → выбери товар → оплати в USDT через CryptoBot\n"
        "2. <b>Эскроу</b> → деньги заморожены до подтверждения получения\n"
        "3. <b>Продавец</b> передаёт товар/услугу прямо в боте\n"
        "4. <b>Ты подтверждаешь</b> → деньги идут продавцу\n"
        "5. <b>Молчишь 48ч</b> → авто-подтверждение\n"
        "6. <b>Проблема</b> → открой спор, разберём вручную\n\n"
        "💰 Комиссия платформы: 10%\n"
        "👥 Рефералы: 50% от комиссии с каждой сделки навсегда\n"
        "⏳ Вывод: через 7 дней после подтверждения получения",
    )


@router.message(F.text == "👥 Реферальная")
async def referral_info(message: Message, user: dict):
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user['ghost_id']}"
    ref_count = await UserService.count_referrals(user["id"])
    await message.answer(
        f"👥 <b>Реферальная программа</b>\n\n"
        f"Приглашай людей — получай <b>50%</b> от комиссии платформы\n"
        f"с каждой их сделки <b>навсегда</b>.\n\n"
        f"Твоя ссылка:\n<code>{escape(ref_link)}</code>\n\n"
        f"Приглашено: <b>{ref_count}</b> чел.",
    )
