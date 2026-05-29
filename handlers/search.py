"""
search.py — поиск по маркету с сортировкой + подписки на категории.
"""
import logging
from html import escape
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import get_db, fmt
from services.listing_service import ListingService
from services.category_service import CategoryService
from services.review_service import ReviewService
from services.subscription_service import SubscriptionService
from .keyboards import listing_card
import i18n

logger = logging.getLogger(__name__)
router = Router()

SORT_OPTIONS = {
    "new":        ("created_at DESC",  "🆕 Newest"),
    "old":        ("created_at ASC",   "🕰 Oldest"),
    "price_asc":  ("price ASC",        "💵 Price ↑"),
    "price_desc": ("price DESC",       "💵 Price ↓"),
    "rating":     ("avg_rating DESC",  "⭐ Rating"),
}
SORT_OPTIONS_RU = {
    "new":        "🆕 Новые",
    "price_asc":  "💵 Цена ↑",
    "price_desc": "💵 Цена ↓",
    "rating":     "⭐ Рейтинг",
}

ITEMS_PER_PAGE = 5


class SearchState(StatesGroup):
    query = State()


def _sort_keyboard(query: str, sort: str, offset: int, lang: str = "en") -> "InlineKeyboardMarkup":
    kb = InlineKeyboardBuilder()
    for key, (_, label_en) in SORT_OPTIONS.items():
        label = SORT_OPTIONS_RU.get(key, label_en) if lang == "ru" else label_en
        mark = "✓ " if key == sort else ""
        kb.button(text=f"{mark}{label}", callback_data=f"search_sort:{key}:{offset}:{query[:50]}")
    kb.adjust(3)
    return kb.as_markup()


# ─── Поиск ───────────────────────────────────────────────────────────────────

@router.message(F.text.in_({"🔍 Search", "🔍 Поиск"}))
async def search_start(message: Message, state: FSMContext, user: dict):
    await state.clear()
    await state.set_state(SearchState.query)
    lang = user.get("lang", "en")
    await message.answer(
        "🔍 Enter search query:" if lang == "en" else "🔍 Введи поисковый запрос:"
    )


@router.message(SearchState.query)
async def search_execute(message: Message, state: FSMContext, user: dict):
    if not message.text:
        return
    query = message.text.strip()
    if len(query) < 2:
        lang = user.get("lang", "en")
        await message.answer("Min 2 characters." if lang == "en" else "Минимум 2 символа.")
        return
    await state.clear()
    await _send_search_results(message, query=query, sort="new", offset=0, user=user)


@router.callback_query(F.data.startswith("search_sort:"))
async def search_sort(callback: CallbackQuery, user: dict):
    parts = callback.data.split(":")
    sort = parts[1]
    offset = int(parts[2])
    query = parts[3]
    await _send_search_results(callback.message, query=query, sort=sort, offset=offset, user=user)
    await callback.answer()


@router.callback_query(F.data.startswith("search_page:"))
async def search_page(callback: CallbackQuery, user: dict):
    parts = callback.data.split(":")
    offset = int(parts[1])
    sort = parts[2]
    query = parts[3]
    await _send_search_results(callback.message, query=query, sort=sort, offset=offset, user=user)
    await callback.answer()


async def _send_search_results(message: Message, query: str, sort: str, offset: int, user: dict):
    lang = user.get("lang", "en")
    sort_sql, _ = SORT_OPTIONS.get(sort, SORT_OPTIONS["new"])
    db = await get_db()

    # Для сортировки по рейтингу нужен JOIN с reviews
    if sort == "rating":
        sql = f"""
            SELECT l.*, u.ghost_id as seller_ghost,
                   COALESCE(AVG(r.rating), 0) as avg_rating
            FROM listings l
            JOIN users u ON l.seller_id = u.id
            LEFT JOIN reviews r ON r.target_id = l.seller_id
            WHERE l.is_active = 1
            AND (l.title LIKE ? OR l.description LIKE ?)
            GROUP BY l.id
            ORDER BY {sort_sql}
            LIMIT ? OFFSET ?
        """
    else:
        sql = f"""
            SELECT l.*, u.ghost_id as seller_ghost
            FROM listings l
            JOIN users u ON l.seller_id = u.id
            WHERE l.is_active = 1
            AND (l.title LIKE ? OR l.description LIKE ?)
            ORDER BY l.is_boosted DESC, {sort_sql}
            LIMIT ? OFFSET ?
        """

    like = f"%{query}%"
    async with db.execute(sql, (like, like, ITEMS_PER_PAGE + 1, offset)) as cur:
        rows = await cur.fetchall()

    has_next = len(rows) > ITEMS_PER_PAGE
    listings = rows[:ITEMS_PER_PAGE]

    if not listings:
        no_results = "No results found." if lang == "en" else "Ничего не найдено."
        await message.answer(no_results)
        return

    header = (
        f"🔍 <b>Results for «{escape(query)}»</b> ({offset + 1}–{offset + len(listings)})"
        if lang == "en" else
        f"🔍 <b>Результаты «{escape(query)}»</b> ({offset + 1}–{offset + len(listings)})"
    )
    await message.answer(header, reply_markup=_sort_keyboard(query, sort, offset, lang))

    last_idx = len(listings) - 1
    for i, lst in enumerate(listings):
        summary = await ReviewService.get_user_summary(lst["seller_id"])
        rating_str = f"⭐ {summary['avg']:.1f} ({summary['count']})" if summary["count"] > 0 else "⭐ —"
        boost_mark = "🚀 " if lst["is_boosted"] else ""
        cat_label = ""
        if lst["category_id"]:
            path = await CategoryService.get_path(lst["category_id"])
            if path:
                cat_label = "\n📂 " + escape(" → ".join(f"{p['emoji']} {p['name']}" for p in path))

        text = (
            f"{boost_mark}<b>{escape(lst['title'])}</b>{cat_label}\n"
            f"{escape(lst['description'][:150])}\n"
            f"💵 <b>{fmt(lst['price'])} USDT</b>  |  {rating_str}\n"
            f"👤 <code>{escape(lst['seller_ghost'])}</code>"
        )

        if i == last_idx and (has_next or offset > 0):
            kb = InlineKeyboardBuilder()
            kb.button(text="💰 Buy" if lang == "en" else "💰 Купить", callback_data=f"buy:{lst['id']}")
            kb.button(text="⭐ Reviews" if lang == "en" else "⭐ Отзывы", callback_data=f"reviews:{lst['seller_id']}")
            kb.adjust(2)
            if offset > 0:
                kb.row()
                kb.button(text="◀️", callback_data=f"search_page:{offset - ITEMS_PER_PAGE}:{sort}:{query[:50]}")
            if has_next:
                if offset == 0:
                    kb.row()
                kb.button(text="▶️", callback_data=f"search_page:{offset + ITEMS_PER_PAGE}:{sort}:{query[:50]}")
            await message.answer(text, reply_markup=kb.as_markup())
        else:
            await message.answer(text, reply_markup=listing_card(lst["id"], lst["seller_id"]))


# ─── Подписки на категории ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("subscribe:"))
async def subscribe_category(callback: CallbackQuery, user: dict):
    cat_id = int(callback.data.split(":")[1])
    cat = await CategoryService.get_by_id(cat_id)
    if not cat:
        await callback.answer("Not found.", show_alert=True)
        return
    lang = user.get("lang", "en")
    created = await SubscriptionService.subscribe(user["id"], cat_id)
    if created:
        await callback.answer(
            f"✅ Subscribed to {cat['emoji']} {cat['name']}"
            if lang == "en" else
            f"✅ Подписан на {cat['emoji']} {cat['name']}",
            show_alert=True,
        )
    else:
        # Уже подписан — отписываемся
        await SubscriptionService.unsubscribe(user["id"], cat_id)
        await callback.answer(
            f"🔕 Unsubscribed from {cat['name']}"
            if lang == "en" else
            f"🔕 Отписан от {cat['name']}",
            show_alert=True,
        )


@router.message(F.text.in_({"🔔 Subscriptions", "🔔 Подписки"}))
async def my_subscriptions(message: Message, user: dict):
    subs = await SubscriptionService.get_user_subscriptions(user["id"])
    lang = user.get("lang", "en")
    if not subs:
        await message.answer(
            "No subscriptions. Subscribe to categories in the Market."
            if lang == "en" else
            "Нет подписок. Подпишись на категории в Маркете."
        )
        return
    lines = ["🔔 <b>Subscriptions:</b>\n" if lang == "en" else "🔔 <b>Подписки:</b>\n"]
    kb = InlineKeyboardBuilder()
    for s in subs:
        lines.append(f"{s['emoji']} {escape(s['name'])}")
        kb.button(text=f"🔕 {s['name']}", callback_data=f"subscribe:{s['category_id']}")
    kb.adjust(2)
    await message.answer("\n".join(lines), reply_markup=kb.as_markup())
