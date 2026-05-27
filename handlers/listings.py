"""
listings.py

Фиксы:
- escape() везде для пользовательских строк
- Pagination кнопка прикрепляется к последнему листингу (меньше сообщений)
- get_by_seller вызывается с LIMIT 20 (не вытаскиваем все из БД)
"""
from html import escape
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import get_db, fmt
from services.listing_service import ListingService, CATEGORY_EMOJI
from .keyboards import listing_card, my_listing_card, category_keyboard, main_menu
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

ITEMS_PER_PAGE = 5
MAX_LISTINGS_VIEW = 20


class CreateListing(StatesGroup):
    title = State()
    description = State()
    price = State()
    category = State()
    file_upload = State()


# ─── Маркет ──────────────────────────────────────────────────────────────────

@router.message(F.text == "🛒 Маркет")
async def show_market(message: Message):
    await _send_market_page(message, offset=0)


@router.callback_query(F.data.startswith("market_page:"))
async def market_page(callback: CallbackQuery):
    offset = int(callback.data.split(":")[1])
    if offset < 0:
        offset = 0
    await _send_market_page(callback.message, offset=offset)
    await callback.answer()


async def _send_market_page(message: Message, offset: int):
    db = await get_db()
    async with db.execute(
        """SELECT l.*, u.ghost_id as seller_ghost
           FROM listings l
           JOIN users u ON l.seller_id = u.id
           WHERE l.is_active = 1
           ORDER BY l.created_at DESC LIMIT ? OFFSET ?""",
        (ITEMS_PER_PAGE + 1, offset),
    ) as cur:
        rows = await cur.fetchall()

    has_next = len(rows) > ITEMS_PER_PAGE
    listings = rows[:ITEMS_PER_PAGE]

    if not listings:
        if offset == 0:
            await message.answer("Маркет пока пустой. Будь первым продавцом! ➕")
        else:
            await message.answer("Больше объявлений нет.")
        return

    await message.answer("🛒 <b>Маркет</b>")
    last_idx = len(listings) - 1

    for i, lst in enumerate(listings):
        emoji = CATEGORY_EMOJI.get(lst["category"], "🔖")
        price_str = fmt(lst["price"])
        text = (
            f"{emoji} <b>{escape(lst['title'])}</b>\n"
            f"{escape(lst['description'][:200])}\n"
            f"💵 <b>{price_str} USDT</b>  |  продавец: <code>{escape(lst['seller_ghost'])}</code>"
        )

        # Последнее сообщение страницы — добавим к нему пагинацию
        if i == last_idx and (has_next or offset > 0):
            kb = InlineKeyboardBuilder()
            kb.button(text="💰 Купить", callback_data=f"buy:{lst['id']}")
            kb.adjust(1)
            if offset > 0:
                kb.row()
                kb.button(text="◀️ Назад", callback_data=f"market_page:{offset - ITEMS_PER_PAGE}")
            if has_next:
                if offset == 0:
                    kb.row()
                kb.button(text="▶️ Ещё", callback_data=f"market_page:{offset + ITEMS_PER_PAGE}")
            await message.answer(text, reply_markup=kb.as_markup())
        else:
            await message.answer(text, reply_markup=listing_card(lst["id"]))


# ─── Создание объявления ─────────────────────────────────────────────────────

@router.message(F.text == "➕ Продать")
async def start_create_listing(message: Message, state: FSMContext):
    await state.set_state(CreateListing.title)
    await message.answer(
        "📝 <b>Новое объявление</b>\n\nВведи название (3–100 символов):",
    )


@router.message(CreateListing.title)
async def listing_title(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, введи текстовое название.")
        return
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("Название слишком короткое. Минимум 3 символа.")
        return
    if len(title) > 100:
        await message.answer("Слишком длинное название. Макс. 100 символов.")
        return
    await state.update_data(title=title)
    await state.set_state(CreateListing.description)
    await message.answer("Опиши, что ты продаёшь (до 1000 символов):")


@router.message(CreateListing.description)
async def listing_desc(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, введи текстовое описание.")
        return
    desc = message.text.strip()
    if len(desc) < 10:
        await message.answer("Описание слишком короткое. Минимум 10 символов.")
        return
    if len(desc) > 1000:
        await message.answer("Слишком длинное описание. Макс. 1000 символов.")
        return
    await state.update_data(description=desc)
    await state.set_state(CreateListing.price)
    await message.answer("💵 Укажи цену в USDT (мин. 0.50, например: 5.00):")


@router.message(CreateListing.price)
async def listing_price(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Введи цену числом.")
        return
    try:
        price = float(message.text.replace(",", ".").strip())
        if price < 0.50:
            await message.answer("Минимальная цена 0.50 USDT.")
            return
        if price > 100_000:
            await message.answer("Максимальная цена 100 000 USDT.")
            return
    except ValueError:
        await message.answer("Некорректная цена. Введи число, например: 5.00")
        return
    await state.update_data(price=price)
    await state.set_state(CreateListing.category)
    await message.answer("Выбери категорию:", reply_markup=category_keyboard())


@router.callback_query(CreateListing.category, F.data.startswith("cat:"))
async def listing_category_cb(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":")[1]
    if category not in ("file", "service", "consultation", "other"):
        await callback.answer("Некорректная категория.", show_alert=True)
        return
    await state.update_data(category=category)
    await state.set_state(CreateListing.file_upload)
    await callback.message.edit_text(
        "📎 Прикрепи файл к объявлению (необязательно).\n"
        "Или напиши <b>нет</b> чтобы пропустить.",
    )
    await callback.answer()


@router.message(CreateListing.category)
async def listing_category_text_fallback(message: Message):
    await message.answer(
        "Пожалуйста, выбери категорию из кнопок 👆",
        reply_markup=category_keyboard(),
    )


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
        await message.answer("Отправь файл или напиши <b>нет</b> чтобы пропустить.")
        return

    data = await state.get_data()
    if not all(k in data for k in ("title", "description", "price", "category")):
        await state.clear()
        await message.answer("Сессия повреждена. Начни заново.", reply_markup=main_menu())
        return

    listing = await ListingService.create(
        seller_id=user["id"],
        title=data["title"],
        description=data["description"],
        price_usdt=data["price"],
        category=data["category"],
        file_id=file_id,
    )
    await state.clear()

    emoji = CATEGORY_EMOJI.get(listing["category"], "🔖")
    price_str = fmt(listing["price"])
    await message.answer(
        f"✅ Объявление опубликовано!\n\n"
        f"{emoji} <b>{escape(listing['title'])}</b>\n"
        f"Цена: <b>{price_str} USDT</b>\n"
        f"ID: <code>{listing['id']}</code>",
        reply_markup=main_menu(),
    )


# ─── Мои товары ──────────────────────────────────────────────────────────────

@router.message(F.text == "📋 Мои товары")
async def my_listings(message: Message, user: dict):
    listings = await ListingService.get_by_seller(user["id"], limit=MAX_LISTINGS_VIEW)
    if not listings:
        await message.answer("У тебя ещё нет объявлений. Нажми ➕ Продать.")
        return
    for lst in listings:
        status = "✅ Активно" if lst["is_active"] else "❌ Снято"
        price_str = fmt(lst["price"])
        text = (
            f"<b>{escape(lst['title'])}</b> — {price_str} USDT\n"
            f"Статус: {status} | ID: <code>{lst['id']}</code>"
        )
        kb = my_listing_card(lst["id"]) if lst["is_active"] else None
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("del_listing:"))
async def deactivate_listing(callback: CallbackQuery, user: dict):
    listing_id = int(callback.data.split(":")[1])
    ok = await ListingService.deactivate(listing_id, user["id"])
    if ok:
        # Не конкатенируем callback.message.text (HTML re-injection).
        # Просто отвечаем и редактируем reply_markup, убирая кнопки.
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.answer("✅ Объявление снято с продажи.", show_alert=True)
    else:
        await callback.answer("Не удалось снять. Проверь, что это твоё объявление.", show_alert=True)
