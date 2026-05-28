"""
listings.py

Фиксы:
- FSM сбрасывается при нажатии любой кнопки главного меню
- i18n для всех текстов
- Кнопка «Предложить категорию» есть и в маркете, и при создании
"""
from html import escape
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import get_db, fmt
from services.listing_service import ListingService
from services.category_service import CategoryService
from services.review_service import ReviewService
from services.user_service import UserService
from config import settings
import i18n
from .keyboards import listing_card, my_listing_card

router = Router()

ITEMS_PER_PAGE = 5
MAX_LISTINGS_VIEW = 20

# Все тексты кнопок меню на обоих языках — для перехвата FSM
_MENU_TEXTS = {
    "🛒 Market", "🛒 Маркет",
    "📦 My Purchases", "📦 Мои покупки",
    "📋 My Listings", "📋 Мои товары",
    "💼 Wallet", "💼 Кошелёк",
    "👥 Referral", "👥 Реферальная",
    "🌐 Language", "🌐 Язык",
}


class CreateListing(StatesGroup):
    title = State()
    description = State()
    price = State()
    root_cat = State()
    sub_cat = State()
    file_upload = State()


class SuggestCategory(StatesGroup):
    name = State()


# ─── FSM guard: сброс при нажатии кнопок меню ────────────────────────────────

@router.message(
    lambda m: m.text in _MENU_TEXTS,
    CreateListing.title,
)
@router.message(
    lambda m: m.text in _MENU_TEXTS,
    CreateListing.description,
)
@router.message(
    lambda m: m.text in _MENU_TEXTS,
    CreateListing.price,
)
@router.message(
    lambda m: m.text in _MENU_TEXTS,
    CreateListing.root_cat,
)
@router.message(
    lambda m: m.text in _MENU_TEXTS,
    CreateListing.sub_cat,
)
@router.message(
    lambda m: m.text in _MENU_TEXTS,
    CreateListing.file_upload,
)
@router.message(
    lambda m: m.text in _MENU_TEXTS,
    SuggestCategory.name,
)
async def fsm_menu_interrupt(message: Message, state: FSMContext, user: dict):
    """Если юзер нажал кнопку меню во время FSM — сбрасываем и передаём управление."""
    await state.clear()
    # Перенаправляем в нужный хендлер вручную
    from handlers.start import main_menu
    if message.text in ("🛒 Market", "🛒 Маркет"):
        await show_market_root(message, user)
    elif message.text in ("➕ Sell", "➕ Продать"):
        await start_create_listing(message, state, user)
    elif message.text in ("📦 My Purchases", "📦 Мои покупки"):
        from handlers.orders import my_purchases
        await my_purchases(message, user)
    elif message.text in ("📋 My Listings", "📋 Мои товары"):
        await my_listings(message, user)
    elif message.text in ("💼 Wallet", "💼 Кошелёк"):
        from handlers.wallet import show_wallet
        await show_wallet(message, user)
    elif message.text in ("👥 Referral", "👥 Реферальная"):
        from handlers.start import referral_info
        await referral_info(message, user)
    elif message.text in ("🌐 Language", "🌐 Язык"):
        from handlers.start import choose_language
        await choose_language(message, user)


# ─── Утилиты клавиатур ───────────────────────────────────────────────────────

async def _root_cats_keyboard(prefix: str, user: dict, with_suggest: bool = True):
    cats = await CategoryService.get_roots()
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=f"{c['emoji']} {c['name']}", callback_data=f"{prefix}:{c['id']}")
    kb.adjust(2)
    if prefix == "mktroot":
        kb.row()
        kb.button(text="📋 All" if user.get("lang") == "en" else "📋 Все", callback_data="mktroot:0")
    if with_suggest:
        kb.row()
        kb.button(text=i18n.get(user, "market_suggest_btn"), callback_data="suggest_cat")
    return kb.as_markup()


async def _sub_cats_keyboard(parent_id: int, prefix: str, user: dict):
    cats = await CategoryService.get_children(parent_id)
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=f"{c['emoji']} {c['name']}", callback_data=f"{prefix}:{c['id']}")
    kb.adjust(2)
    kb.row()
    back = "◀️ Back" if user.get("lang") == "en" else "◀️ Назад"
    if prefix == "picksub":
        kb.button(text="✅ No subcategory" if user.get("lang") == "en" else "✅ Без уточнения",
                  callback_data=f"picksub:parent:{parent_id}")
        kb.button(text=back, callback_data="picksub:back")
    elif prefix == "mktsub":
        kb.button(text=back, callback_data="mktsub:back")
    return kb.as_markup()


# ─── Маркет ──────────────────────────────────────────────────────────────────

@router.message(F.text.in_({"🛒 Market", "🛒 Маркет"}))
async def show_market_root(message: Message, user: dict):
    await message.answer(
        i18n.get(user, "market_choose_cat"),
        reply_markup=await _root_cats_keyboard("mktroot", user, with_suggest=True),
    )


@router.callback_query(F.data.startswith("mktroot:"))
async def market_root_chosen(callback: CallbackQuery, user: dict):
    cat_id = int(callback.data.split(":")[1])
    if cat_id == 0:
        await _send_market_page(callback.message, offset=0, category_id=None, user=user)
        await callback.answer()
        return
    if await CategoryService.has_children(cat_id):
        cat = await CategoryService.get_by_id(cat_id)
        kb = await _sub_cats_keyboard(cat_id, "mktsub", user)
        builder = InlineKeyboardBuilder.from_markup(kb)
        builder.row()
        all_label = f"📋 All in «{cat['name']}»" if user.get("lang") == "en" else f"📋 Все в «{cat['name']}»"
        builder.button(text=all_label, callback_data=f"mktsub:parent:{cat_id}")
        await callback.message.answer(
            f"{cat['emoji']} <b>{escape(cat['name'])}</b>",
            reply_markup=builder.as_markup(),
        )
    else:
        await _send_market_page(callback.message, offset=0, category_id=cat_id, user=user)
    await callback.answer()


@router.callback_query(F.data.startswith("mktsub:"))
async def market_sub_chosen(callback: CallbackQuery, user: dict):
    parts = callback.data.split(":")
    if parts[1] == "back":
        await callback.message.answer(
            i18n.get(user, "market_choose_cat"),
            reply_markup=await _root_cats_keyboard("mktroot", user, with_suggest=True),
        )
        await callback.answer()
        return
    if parts[1] == "parent":
        await _send_market_page(callback.message, offset=0, parent_id=int(parts[2]), user=user)
    else:
        await _send_market_page(callback.message, offset=0, category_id=int(parts[1]), user=user)
    await callback.answer()


@router.callback_query(F.data.startswith("market_page:"))
async def market_page(callback: CallbackQuery, user: dict):
    parts = callback.data.split(":")
    offset = max(0, int(parts[1]))
    cat_id = int(parts[2]) if parts[2] != "n" else None
    parent_id = int(parts[3]) if parts[3] != "n" else None
    await _send_market_page(callback.message, offset=offset, category_id=cat_id, parent_id=parent_id, user=user)
    await callback.answer()


async def _send_market_page(message: Message, offset: int, user: dict,
                             category_id=None, parent_id=None):
    db = await get_db()
    if parent_id is not None:
        sql = """SELECT l.*, u.ghost_id as seller_ghost
                 FROM listings l JOIN users u ON l.seller_id = u.id
                 WHERE l.is_active = 1
                 AND (l.category_id = ? OR l.category_id IN
                      (SELECT id FROM categories WHERE parent_id = ?))
                 ORDER BY l.created_at DESC LIMIT ? OFFSET ?"""
        params = (parent_id, parent_id, ITEMS_PER_PAGE + 1, offset)
    elif category_id is not None:
        sql = """SELECT l.*, u.ghost_id as seller_ghost
                 FROM listings l JOIN users u ON l.seller_id = u.id
                 WHERE l.is_active = 1 AND l.category_id = ?
                 ORDER BY l.created_at DESC LIMIT ? OFFSET ?"""
        params = (category_id, ITEMS_PER_PAGE + 1, offset)
    else:
        sql = """SELECT l.*, u.ghost_id as seller_ghost
                 FROM listings l JOIN users u ON l.seller_id = u.id
                 WHERE l.is_active = 1
                 ORDER BY l.created_at DESC LIMIT ? OFFSET ?"""
        params = (ITEMS_PER_PAGE + 1, offset)

    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()

    has_next = len(rows) > ITEMS_PER_PAGE
    listings = rows[:ITEMS_PER_PAGE]

    if not listings:
        msg = i18n.get(user, "market_empty_cat" if (category_id or parent_id) else "market_empty")
        await message.answer(msg)
        return

    cat_token = str(category_id) if category_id else "n"
    par_token = str(parent_id) if parent_id else "n"
    last_idx = len(listings) - 1

    for i, lst in enumerate(listings):
        summary = await ReviewService.get_user_summary(lst["seller_id"])
        rating_str = (
            f"⭐ {summary['avg']:.1f} ({summary['count']})"
            if summary["count"] > 0 else i18n.get(user, "market_no_reviews")
        )
        cat_label = ""
        if lst["category_id"]:
            path = await CategoryService.get_path(lst["category_id"])
            if path:
                cat_label = "\n📂 " + escape(" → ".join(f"{p['emoji']} {p['name']}" for p in path))

        text = (
            f"<b>{escape(lst['title'])}</b>{cat_label}\n"
            f"{escape(lst['description'][:200])}\n"
            f"💵 <b>{fmt(lst['price'])} USDT</b>\n"
            f"👤 <code>{escape(lst['seller_ghost'])}</code>  |  {rating_str}"
        )

        if i == last_idx and (has_next or offset > 0):
            kb = InlineKeyboardBuilder()
            kb.button(text="💰 Buy" if user.get("lang") == "en" else "💰 Купить",
                      callback_data=f"buy:{lst['id']}")
            kb.button(text="⭐ Reviews" if user.get("lang") == "en" else "⭐ Отзывы",
                      callback_data=f"reviews:{lst['seller_id']}")
            kb.adjust(2)
            if offset > 0:
                kb.row()
                kb.button(text="◀️", callback_data=f"market_page:{offset - ITEMS_PER_PAGE}:{cat_token}:{par_token}")
            if has_next:
                if offset == 0:
                    kb.row()
                kb.button(text="▶️", callback_data=f"market_page:{offset + ITEMS_PER_PAGE}:{cat_token}:{par_token}")
            await message.answer(text, reply_markup=kb.as_markup())
        else:
            await message.answer(text, reply_markup=listing_card(lst["id"], lst["seller_id"]))


# ─── Отзывы ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reviews:"))
async def show_reviews(callback: CallbackQuery, user: dict):
    target_id = int(callback.data.split(":")[1])
    target = await UserService.get_by_id(target_id)
    if not target:
        await callback.answer("Not found." if user.get("lang") == "en" else "Не найдено.", show_alert=True)
        return
    summary = await ReviewService.get_user_summary(target_id)
    reviews = await ReviewService.get_user_reviews(target_id, limit=10)
    if summary["count"] == 0:
        await callback.message.answer(i18n.get(user, "reviews_none", ghost=escape(target["ghost_id"])))
        await callback.answer()
        return
    lines = [i18n.get(user, "reviews_header", ghost=escape(target["ghost_id"]),
                      avg=summary["avg"], count=summary["count"])]
    for r in reviews:
        stars = "⭐" * r["rating"]
        txt = f"\n💬 {escape(r['text'])}" if r.get("text") else ""
        lines.append(f"{stars}  <code>{escape(r['reviewer_ghost'])}</code>  <i>{r['created_at'][:10]}</i>{txt}")
    out = "\n".join(lines)
    if len(out) > 4000:
        out = out[:3990] + "\n..."
    await callback.message.answer(out)
    await callback.answer()


# ─── Создание объявления ─────────────────────────────────────────────────────

@router.message(F.text.in_({"➕ Sell", "➕ Продать"}))
async def start_create_listing(message: Message, state: FSMContext, user: dict):
    await state.clear()
    await state.set_state(CreateListing.title)
    await message.answer(i18n.get(user, "sell_start"))


@router.message(CreateListing.title)
async def listing_title(message: Message, state: FSMContext, user: dict):
    if not message.text:
        await message.answer(i18n.get(user, "sell_title_text"))
        return
    title = message.text.strip()
    if len(title) < 3:
        await message.answer(i18n.get(user, "sell_title_short"))
        return
    if len(title) > 100:
        await message.answer(i18n.get(user, "sell_title_long"))
        return
    await state.update_data(title=title)
    await state.set_state(CreateListing.description)
    await message.answer(i18n.get(user, "sell_desc_prompt"))


@router.message(CreateListing.description)
async def listing_desc(message: Message, state: FSMContext, user: dict):
    if not message.text:
        await message.answer(i18n.get(user, "sell_desc_text"))
        return
    desc = message.text.strip()
    if len(desc) < 10:
        await message.answer(i18n.get(user, "sell_desc_short"))
        return
    if len(desc) > 1000:
        await message.answer(i18n.get(user, "sell_desc_long"))
        return
    await state.update_data(description=desc)
    await state.set_state(CreateListing.price)
    await message.answer(i18n.get(user, "sell_price_prompt"))


@router.message(CreateListing.price)
async def listing_price(message: Message, state: FSMContext, user: dict):
    if not message.text:
        await message.answer(i18n.get(user, "sell_price_text"))
        return
    try:
        price = float(message.text.replace(",", ".").strip())
        if price < 0.50:
            await message.answer(i18n.get(user, "sell_price_min"))
            return
        if price > 100_000:
            await message.answer(i18n.get(user, "sell_price_max"))
            return
    except ValueError:
        await message.answer(i18n.get(user, "sell_price_invalid"))
        return
    await state.update_data(price=price)
    await state.set_state(CreateListing.root_cat)
    await message.answer(
        i18n.get(user, "sell_cat_prompt"),
        reply_markup=await _root_cats_keyboard("pickroot", user, with_suggest=True),
    )


@router.callback_query(CreateListing.root_cat, F.data == "suggest_cat")
async def suggest_from_create(callback: CallbackQuery, state: FSMContext, user: dict):
    await state.set_state(SuggestCategory.name)
    await callback.message.answer(i18n.get(user, "sell_suggest_cat"))
    await callback.answer()


@router.callback_query(CreateListing.root_cat, F.data.startswith("pickroot:"))
async def listing_root_chosen(callback: CallbackQuery, state: FSMContext, user: dict):
    root_id = int(callback.data.split(":")[1])
    cat = await CategoryService.get_by_id(root_id)
    if not cat:
        await callback.answer("Not found.", show_alert=True)
        return
    if await CategoryService.has_children(root_id):
        await state.update_data(root_id=root_id)
        await state.set_state(CreateListing.sub_cat)
        await callback.message.edit_text(
            i18n.get(user, "sell_subcat_prompt", emoji=cat["emoji"], name=escape(cat["name"])),
            reply_markup=await _sub_cats_keyboard(root_id, "picksub", user),
        )
    else:
        await state.update_data(category_id=root_id)
        await state.set_state(CreateListing.file_upload)
        path = await CategoryService.get_path(root_id)
        label = escape(" → ".join(f"{p['emoji']} {p['name']}" for p in path))
        await callback.message.edit_text(i18n.get(user, "sell_file_prompt", label=label))
    await callback.answer()


@router.callback_query(CreateListing.sub_cat, F.data.startswith("picksub:"))
async def listing_sub_chosen(callback: CallbackQuery, state: FSMContext, user: dict):
    parts = callback.data.split(":")
    if parts[1] == "back":
        await state.set_state(CreateListing.root_cat)
        await callback.message.edit_text(
            i18n.get(user, "sell_cat_prompt"),
            reply_markup=await _root_cats_keyboard("pickroot", user, with_suggest=True),
        )
        await callback.answer()
        return
    cat_id = int(parts[2]) if parts[1] == "parent" else int(parts[1])
    cat = await CategoryService.get_by_id(cat_id)
    if not cat:
        await callback.answer("Not found.", show_alert=True)
        return
    await state.update_data(category_id=cat_id)
    await state.set_state(CreateListing.file_upload)
    path = await CategoryService.get_path(cat_id)
    label = escape(" → ".join(f"{p['emoji']} {p['name']}" for p in path))
    await callback.message.edit_text(i18n.get(user, "sell_file_prompt", label=label))
    await callback.answer()


@router.message(CreateListing.root_cat)
@router.message(CreateListing.sub_cat)
async def listing_category_text_fallback(message: Message, user: dict):
    await message.answer(i18n.get(user, "sell_cat_buttons"))


@router.message(CreateListing.file_upload)
async def listing_file(message: Message, state: FSMContext, user: dict):
    file_id = None
    if message.document:
        file_id = message.document.file_id
    elif message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.audio:
        file_id = message.audio.file_id
    elif message.text and message.text.strip().lower() in ("нет", "no", "-", "skip"):
        file_id = None
    else:
        await message.answer(i18n.get(user, "sell_file_hint"))
        return

    data = await state.get_data()
    if not all(k in data for k in ("title", "description", "price", "category_id")):
        await state.clear()
        from handlers.start import main_menu
        await message.answer(i18n.get(user, "sell_session_broken"), reply_markup=main_menu(user))
        return

    cat = await CategoryService.get_by_id(data["category_id"])
    listing = await ListingService.create(
        seller_id=user["id"],
        title=data["title"],
        description=data["description"],
        price_usdt=data["price"],
        category=(cat["name"] if cat else "other"),
        category_id=data["category_id"],
        file_id=file_id,
    )
    await state.clear()

    path = await CategoryService.get_path(listing["category_id"]) if listing.get("category_id") else []
    label = escape(" → ".join(f"{p['emoji']} {p['name']}" for p in path)) if path else "—"

    from handlers.start import main_menu
    await message.answer(
        i18n.get(user, "sell_published",
                 title=escape(listing["title"]),
                 price=fmt(listing["price"]),
                 label=label,
                 id=listing["id"]),
        reply_markup=main_menu(user),
    )


# ─── Предложить категорию (в любой момент) ───────────────────────────────────

@router.callback_query(F.data == "suggest_cat")
async def suggest_cat_anytime(callback: CallbackQuery, state: FSMContext, user: dict):
    await state.clear()
    await state.set_state(SuggestCategory.name)
    await callback.message.answer(i18n.get(user, "sell_suggest_cat"))
    await callback.answer()


@router.message(SuggestCategory.name)
async def suggest_cat_save(message: Message, state: FSMContext, user: dict, bot: Bot):
    if not message.text:
        await message.answer(i18n.get(user, "sell_suggest_invalid"))
        return
    text = message.text.strip()
    if len(text) < 2 or len(text) > 100:
        await message.answer(i18n.get(user, "sell_suggest_invalid"))
        return
    suggestion = await CategoryService.suggest(user["id"], text)
    await state.clear()
    for admin_id in settings.get_admin_ids():
        try:
            await bot.send_message(
                admin_id,
                f"💡 <b>Category suggestion #{suggestion['id']}</b>\n"
                f"From: <code>{escape(user['ghost_id'])}</code>\n"
                f"Name: «{escape(text)}»",
            )
        except Exception:
            pass
    from handlers.start import main_menu
    await message.answer(i18n.get(user, "sell_suggest_sent"), reply_markup=main_menu(user))


# ─── Мои товары ──────────────────────────────────────────────────────────────

@router.message(F.text.in_({"📋 My Listings", "📋 Мои товары"}))
async def my_listings(message: Message, user: dict):
    listings = await ListingService.get_by_seller(user["id"], limit=MAX_LISTINGS_VIEW)
    if not listings:
        from handlers.start import main_menu
        await message.answer(
            "No listings yet." if user.get("lang") == "en" else "Объявлений нет. ➕",
        )
        return
    for lst in listings:
        status = "✅" if lst["is_active"] else "❌"
        cat_label = ""
        if lst["category_id"]:
            path = await CategoryService.get_path(lst["category_id"])
            if path:
                cat_label = "\n📂 " + escape(" → ".join(f"{p['emoji']} {p['name']}" for p in path))
        await message.answer(
            f"<b>{escape(lst['title'])}</b> — {fmt(lst['price'])} USDT{cat_label}\n"
            f"{status} ID: <code>{lst['id']}</code> | {lst['created_at'][:10]}",
            reply_markup=my_listing_card(lst["id"]) if lst["is_active"] else None,
        )


@router.callback_query(F.data.startswith("del_listing:"))
async def deactivate_listing(callback: CallbackQuery, user: dict):
    listing_id = int(callback.data.split(":")[1])
    ok = await ListingService.deactivate(listing_id, user["id"])
    if ok:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.answer("✅ Removed." if user.get("lang") == "en" else "✅ Снято.", show_alert=True)
    else:
        await callback.answer("Failed." if user.get("lang") == "en" else "Не удалось.", show_alert=True)
