"""
boost.py — платный буст объявлений.
Вызывается из «Мои товары» → кнопка 🚀 Boost.
"""
import logging
from html import escape
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.boost_service import BoostService, BOOST_PLANS
from services.listing_service import ListingService
from database.db import fmt, to_micro

logger = logging.getLogger(__name__)
router = Router()


def _boost_plans_keyboard(listing_id: int, lang: str = "en") -> "InlineKeyboardMarkup":
    kb = InlineKeyboardBuilder()
    for plan in BOOST_PLANS:
        kb.button(
            text=f"🚀 {plan['label']}",
            callback_data=f"boost_buy:{listing_id}:{plan['hours']}",
        )
    kb.adjust(1)
    kb.row()
    kb.button(
        text="❌ Cancel" if lang == "en" else "❌ Отмена",
        callback_data="boost_cancel",
    )
    return kb.as_markup()


@router.callback_query(F.data.startswith("boost:"))
async def boost_menu(callback: CallbackQuery, user: dict):
    listing_id = int(callback.data.split(":")[1])
    listing = await ListingService.get_by_id(listing_id)
    if not listing or listing["seller_id"] != user["id"]:
        await callback.answer("No access." if user.get("lang") == "en" else "Нет доступа.", show_alert=True)
        return

    lang = user.get("lang", "en")
    active = await BoostService.get_active_boost(listing_id)
    boost_info = ""
    if active:
        boost_info = (
            f"\n⚡ Active boost until: {active['expires_at'][:16]}"
            if lang == "en" else
            f"\n⚡ Активный буст до: {active['expires_at'][:16]}"
        )

    from database.db import fmt as _fmt
    balance_str = _fmt(user["balance"])
    await callback.message.answer(
        (
            f"🚀 <b>Boost listing</b>\n"
            f"<b>{escape(listing['title'])}</b>{boost_info}\n\n"
            f"Your balance: {balance_str} USDT\n\n"
            f"Choose a plan:"
        ) if lang == "en" else (
            f"🚀 <b>Буст объявления</b>\n"
            f"<b>{escape(listing['title'])}</b>{boost_info}\n\n"
            f"Твой баланс: {balance_str} USDT\n\n"
            f"Выбери тариф:"
        ),
        reply_markup=_boost_plans_keyboard(listing_id, lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("boost_buy:"))
async def boost_buy(callback: CallbackQuery, user: dict):
    parts = callback.data.split(":")
    listing_id = int(parts[1])
    hours = int(parts[2])

    plan = next((p for p in BOOST_PLANS if p["hours"] == hours), None)
    if not plan:
        await callback.answer("Invalid plan.", show_alert=True)
        return

    listing = await ListingService.get_by_id(listing_id)
    if not listing or listing["seller_id"] != user["id"]:
        await callback.answer("No access." if user.get("lang") == "en" else "Нет доступа.", show_alert=True)
        return

    ok = await BoostService.apply_boost(
        listing_id=listing_id,
        user_id=user["id"],
        hours=hours,
        price_usdt=plan["price_usdt"],
    )

    lang = user.get("lang", "en")
    if ok:
        await callback.message.answer(
            f"🚀 Boost activated for {hours}h! -{plan['price_usdt']} USDT"
            if lang == "en" else
            f"🚀 Буст активирован на {hours}ч! -{plan['price_usdt']} USDT"
        )
    else:
        await callback.answer(
            "Insufficient balance." if lang == "en" else "Недостаточно средств.",
            show_alert=True,
        )
    await callback.answer()


@router.callback_query(F.data == "boost_cancel")
async def boost_cancel(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
