"""
listings.py

Динамические категории:
- При создании: выбор root → child (или сразу publish если у root нет детей)
- Кнопка «Предложить категорию» → отправляет заявку админам
- При просмотре маркета: меню root-категорий → листинг по категории
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
from .keyboards import listing_card, my_listing_card, main_menu

router = Router()

ITEMS_PER_PAGE = 5
MAX_LISTINGS_VIEW = 20


class CreateListing(StatesGroup):
    title = State()
    description = State()
    price = State()
    root_cat = State()
    sub_cat = State()
    file_upload = State()


class SuggestCategory(StatesGroup):
    name = State()


# ─── Утилита: клавиатура с категориями ───────────────────────────────────────

async def _root_cats_keyboard(prefix: str, with_suggest: bool = True):
    """
    prefix: 'pickroot' (создание) или 'mktroot' (фильтр маркета)
    Кнопки рядов по 2.
    """
    cats = await CategoryService.get_roots()
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(
            text=f"{c['emoji']} {c['name']}",
            callback_data=f"{prefix}:{c['id']}",
        )
    kb.adjust(2)
    if prefix == "mktroot":
        kb.row()
        kb.button(text="📋 Все объявления", callback_data="mktroot:0")
    if with_suggest and prefix == "pickroot":
        kb.row()
        kb.button(text="➕ Предложить категорию", callback_data="suggest_cat")
    return kb.as_markup()


async def _sub_cats_keyboard(parent_id: int, prefix: str):
    cats = await CategoryService.get_children(parent_id)
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=f"{c['emoji']} {c['name']}", callback_data=f"{prefix}:{c['id']}")
    kb.adjust(2)
    kb.row()
    if prefix == "picksub":
        # При создании: разрешим выбрать сам родитель если хочется без подкатегории
        kb.button(text="✅ Без уточнения", callback_data=f"picksub:parent:{parent_id}")
        kb.button(text="◀️ Назад", callback_data="picksub:back")
        kb.adjust(2, 2)
    elif prefix == "mktsub":
        kb.button(text="◀️ Назад", callback_data="mktsub:back")
    return kb.as_markup()


# ─── Маркет: фильтр по категории ─────────────────────────────────────────────

@router.message(F.text == "🛒 Маркет")
async def show_market_root(message: Message):
    await message.answer(
        "🛒 <b>Маркет Anonex</b>\nВыбери категорию:",
        reply_markup=await _root_cats_keyboard("mktroot", with_suggest=False),
    )


@router.callback_query(F.data.startswith("mktroot:"))
async def market_root_chosen(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[1])

    if cat_id == 0:
        # Все объявления
        await _send_market_page(callback.message, offset=0, category_id=None)
        await callback.answer()
        return

    # Если у категории есть дети — показываем подкатегории
    if await CategoryService.has_children(cat_id):
        cat = await CategoryService.get_by_id(cat_id)
        kb = await _sub_cats_keyboard(cat_id, "mktsub")
        # Кнопка «Все в этой категории»
        builder = InlineKeyboardBuilder.from_markup(kb)
        builder.row()
        builder.button(text=f"📋 Все в «{cat['name']}»", callback_data=f"mktsub:parent:{cat_id}")
        await callback.message.answer(
            f"{cat['emoji']} <b>{escape(cat['name'])}</b> — выбери подкатегорию:",
            reply_markup=builder.as_markup(),
        )
        await callback.answer()
        return

    # Нет детей — сразу выводим листинги
    await _send_market_page(callback.message, offset=0, category_id=cat_id)
    await callback.answer()


@router.callback_query(F.data.startswith("mktsub:"))
async def market_sub_chosen(callback: CallbackQuery):
    parts = callback.data.split(":")
    if parts[1] == "back":
        await callback.message.answer(
            "🛒 Выбери категорию:",
            reply_markup=await _root_cats_keyboard("mktroot", with_suggest=False),
        )
        await callback.answer()
        return
    if parts[1] == "parent":
        # Все в род-категории — показываем листинги корневой категории и всех её детей
        parent_id = int(parts[2])
        await _send_market_page(callback.message, offset=0, parent_id=parent_id)
        await callback.answer()
        return
    cat_id = int(parts[1])
    await _send_market_page(callback.message, offset=0, category_id=cat_id)
    await callback.answer()


@router.callback_query(F.data.startswith("market_page:"))
async def market_page(callback: CallbackQuery):
    # callback_data: market_page:<offset>:<cat_id>:<parent_id>
    parts = callback.data.split(":")
    offset = max(0, int(parts[1]))
    cat_id = int(parts[2]) if parts[2] != "n" else None
    parent_id = int(parts[3]) if parts[3] != "n" else None
    await _send_market_page(callback.message, offset=offset, category_id=cat_id, parent_id=parent_id)
    await callback.answer()


async def _send_market_page(message: Message, offset: int, category_id=None, parent_id=None):
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
        await message.answer(
            "В этой категории пока нет объявлений." if offset == 0
            else "Больше нет."
        )
        return

    last_idx = len(listings) - 1
    cat_token = str(category_id) if category_id else "n"
    par_token = str(parent_id) if parent_id else "n"

    for i, lst in enumerate(listings):
        summary = await ReviewService.get_user_summary(lst["seller_id"])
        rating_str = (
            f"⭐ {summary['avg']:.1f} ({summary['count']})"
            if summary["count"] > 0 else "⭐ нет отзывов"
        )

        # Категория
        cat_label = ""
        if lst["category_id"]:
            path = await CategoryService.get_path(lst["category_id"])
            if path:
                cat_label = " → ".join(f"{p['emoji']} {p['name']}" for p in path)
                cat_label = f"\n📂 {escape(cat_label)}"

        text = (
            f"<b>{escape(lst['title'])}</b>{cat_label}\n"
            f"{escape(lst['description'][:200])}\n"
            f"💵 <b>{fmt(lst['price'])} USDT</b>\n"
            f"👤 <code>{escape(lst['seller_ghost'])}</code>  |  {rating_str}"
        )

        if i == last_idx and (has_next or offset > 0):
            kb = InlineKeyboardBuilder()
            kb.button(text="💰 Купить", callback_data=f"buy:{lst['id']}")
            kb.button(text="⭐ Отзывы", callback_data=f"reviews:{lst['seller_id']}")
            kb.adjust(2)
            if offset > 0:
                kb.row()
                kb.button(
                    text="◀️ Назад",
                    callback_data=f"market_page:{offset - ITEMS_PER_PAGE}:{cat_token}:{par_token}",
                )
            if has_next:
                if offset == 0:
                    kb.row()
                kb.button(
                    text="▶️ Ещё",
                    callback_data=f"market_page:{offset + ITEMS_PER_PAGE}:{cat_token}:{par_token}",
                )
            await message.answer(text, reply_markup=kb.as_markup())
        else:
            await message.answer(text, reply_markup=listing_card(lst["id"], lst["seller_id"]))


# ─── Просмотр отзывов ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reviews:"))
async def show_reviews(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    target = await UserService.get_by_id(user_id)
    if not target:
        await callback.answer("Не найдено.", show_alert=True)
        return

    summary = await ReviewService.get_user_summary(user_id)
    reviews = await ReviewService.get_user_reviews(user_id, limit=10)

    if summary["count"] == 0:
        await callback.message.answer(f"⭐ <b>{escape(target['ghost_id'])}</b>\n\nОтзывов пока нет.")
        await callback.answer()
        return

    lines = [
        f"⭐ <b>{escape(target['ghost_id'])}</b>",
        f"Средняя: <b>{summary['avg']:.1f}</b> / 5  ({summary['count']})\n",
    ]
    for r in reviews:
        stars = "⭐" * r["rating"]
        text = f"\n💬 {escape(r['text'])}" if r.get("text") else ""
        lines.append(
            f"{stars}  <code>{escape(r['reviewer_ghost'])}</code>  "
            f"<i>{r['created_at'][:10]}</i>{text}"
        )

    out = "\n".join(lines)
    if len(out) > 4000:
        out = out[:3990] + "\n..."
    await callback.message.answer(out)
    await callback.answer()


# ─── Создание объявления ─────────────────────────────────────────────────────

@router.message(F.text == "➕ Продать")
async def start_create_listing(message: Message, state: FSMContext):
    await state.set_state(CreateListing.title)
    await message.answer(
        "📝 <b>Новое объявление</b>\n\n"
        "<i>Активно 30 дней.</i>\n\n"
        "Введи название (3–100 символов):",
    )


@router.message(CreateListing.title)
async def listing_title(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Введи текст.")
        return
    title = message.text.strip()
    if len(title) < 3 or len(title) > 100:
        await message.answer("3–100 символов.")
        return
    await state.update_data(title=title)
    await state.set_state(CreateListing.description)
    await message.answer("Описание (10–1000):")


@router.message(CreateListing.description)
async def listing_desc(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Введи текст.")
        return
    desc = message.text.strip()
    if len(desc) < 10 or len(desc) > 1000:
        await message.answer("10–1000 символов.")
        return
    await state.update_data(description=desc)
    await state.set_state(CreateListing.price)
    await message.answer("💵 Цена в USDT (мин. 0.50):")


@router.message(CreateListing.price)
async def listing_price(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Введи число.")
        return
    try:
        price = float(message.text.replace(",", ".").strip())
        if price < 0.50 or price > 100_000:
            await message.answer("0.50 — 100 000 USDT.")
            return
    except ValueError:
        await message.answer("Например: 5.00")
        return
    await state.update_data(price=price)
    await state.set_state(CreateListing.root_cat)
    await message.answer(
        "Выбери категорию:",
        reply_markup=await _root_cats_keyboard("pickroot", with_suggest=True),
    )


@router.callback_query(CreateListing.root_cat, F.data == "suggest_cat")
async def suggest_from_create(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SuggestCategory.name)
    await callback.message.answer(
        "💡 Напиши название категории, которую хочешь добавить.\n"
        "Можно указать раздел: например <i>Игры → My Game Title</i>.\n"
        "Админ рассмотрит вручную.",
    )
    await callback.answer()


@router.callback_query(CreateListing.root_cat, F.data.startswith("pickroot:"))
async def listing_root_chosen(callback: CallbackQuery, state: FSMContext):
    root_id = int(callback.data.split(":")[1])
    cat = await CategoryService.get_by_id(root_id)
    if not cat:
        await callback.answer("Не найдено.", show_alert=True)
        return

    if await CategoryService.has_children(root_id):
        await state.update_data(root_id=root_id)
        await state.set_state(CreateListing.sub_cat)
        await callback.message.edit_text(
            f"{cat['emoji']} <b>{escape(cat['name'])}</b>\nВыбери подкатегорию:",
            reply_markup=await _sub_cats_keyboard(root_id, "picksub"),
        )
    else:
        await state.update_data(category_id=root_id)
        await state.set_state(CreateListing.file_upload)
        await callback.message.edit_text(
            f"Категория: {cat['emoji']} {escape(cat['name'])}\n\n"
            "📎 Прикрепи файл к объявлению (необязательно).\n"
            "Или напиши <b>нет</b> чтобы пропустить.",
        )
    await callback.answer()


@router.callback_query(CreateListing.sub_cat, F.data.startswith("picksub:"))
async def listing_sub_chosen(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if parts[1] == "back":
        await state.set_state(CreateListing.root_cat)
        await callback.message.edit_text(
            "Выбери категорию:",
            reply_markup=await _root_cats_keyboard("pickroot", with_suggest=True),
        )
        await callback.answer()
        return
    if parts[1] == "parent":
        cat_id = int(parts[2])
    else:
        cat_id = int(parts[1])

    cat = await CategoryService.get_by_id(cat_id)
    if not cat:
        await callback.answer("Не найдено.", show_alert=True)
        return

    await state.update_data(category_id=cat_id)
    await state.set_state(CreateListing.file_upload)
    path = await CategoryService.get_path(cat_id)
    label = " → ".join(f"{p['emoji']} {p['name']}" for p in path)
    await callback.message.edit_text(
        f"Категория: {escape(label)}\n\n"
        "📎 Прикрепи файл (необязательно).\n"
        "Или напиши <b>нет</b> чтобы пропустить.",
    )
    await callback.answer()


@router.message(CreateListing.root_cat)
@router.message(CreateListing.sub_cat)
async def listing_category_text_fallback(message: Message):
    await message.answer("Используй кнопки выше 👆")


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
        await message.answer("Файл или <b>нет</b>.")
        return

    data = await state.get_data()
    if not all(k in data for k in ("title", "description", "price", "category_id")):
        await state.clear()
        await message.answer("Сессия повреждена. Начни заново.", reply_markup=main_menu())
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
    label = " → ".join(f"{p['emoji']} {p['name']}" for p in path) if path else "—"

    await message.answer(
        f"✅ Опубликовано! Активно 30 дней.\n\n"
        f"<b>{escape(listing['title'])}</b> — <b>{fmt(listing['price'])} USDT</b>\n"
        f"📂 {escape(label)}\n"
        f"ID: <code>{listing['id']}</code>",
        reply_markup=main_menu(),
    )


# ─── Предложение категории (вне FSM создания) ────────────────────────────────

@router.callback_query(F.data == "suggest_cat")
async def suggest_cat_anytime(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(SuggestCategory.name)
    await callback.message.answer(
        "💡 Напиши название категории, которую хочешь добавить:",
    )
    await callback.answer()


@router.message(SuggestCategory.name)
async def suggest_cat_save(message: Message, state: FSMContext, user: dict, bot: Bot):
    if not message.text:
        await message.answer("Введи название текстом.")
        return
    text = message.text.strip()
    if len(text) < 2 or len(text) > 100:
        await message.answer("2–100 символов.")
        return

    suggestion = await CategoryService.suggest(user["id"], text)
    await state.clear()

    # Уведомляем админов
    for admin_id in settings.get_admin_ids():
        try:
            await bot.send_message(
                admin_id,
                f"💡 <b>Новая категория #{suggestion['id']}</b>\n"
                f"От: <code>{escape(user['ghost_id'])}</code>\n"
                f"Название: «{escape(text)}»",
            )
        except Exception:
            pass

    await message.answer(
        f"✅ Заявка отправлена. Админ рассмотрит её и добавит категорию если она актуальна.",
        reply_markup=main_menu(),
    )


# ─── Мои товары ──────────────────────────────────────────────────────────────

@router.message(F.text == "📋 Мои товары")
async def my_listings(message: Message, user: dict):
    listings = await ListingService.get_by_seller(user["id"], limit=MAX_LISTINGS_VIEW)
    if not listings:
        await message.answer("Объявлений нет. ➕ Продать.")
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
        await callback.answer("✅ Снято.", show_alert=True)
    else:
        await callback.answer("Не удалось.", show_alert=True)
