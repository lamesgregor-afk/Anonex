"""
database/db.py — миграции v1 + v2.
v2 добавляет таблицу reviews и индексы.
"""
import os
import aiosqlite
import asyncio
import contextlib
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "anonex.db")

_db: Optional[aiosqlite.Connection] = None
_db_lock = asyncio.Lock()
_write_lock = asyncio.Lock()


def to_micro(usdt: float) -> int:
    from decimal import Decimal, ROUND_HALF_UP
    return int(
        Decimal(str(usdt)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        * 1_000_000
    )


def fmt(micro: int, decimals: int = 4) -> str:
    from decimal import Decimal
    if decimals <= 0:
        return str(int(Decimal(micro) / Decimal(1_000_000)))
    val = (Decimal(micro) / Decimal(1_000_000)).quantize(
        Decimal("0." + "0" * decimals)
    )
    return str(val)


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        async with _db_lock:
            if _db is None:
                conn = await aiosqlite.connect(DB_PATH)
                conn.row_factory = aiosqlite.Row
                await conn.execute("PRAGMA journal_mode=WAL")
                await conn.execute("PRAGMA foreign_keys=ON")
                await conn.execute("PRAGMA busy_timeout=5000")
                _db = conn
    return _db


@contextlib.asynccontextmanager
async def transaction():
    db = await get_db()
    async with _write_lock:
        try:
            await db.execute("BEGIN IMMEDIATE")
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def _get_user_version(db) -> int:
    async with db.execute("PRAGMA user_version") as cur:
        row = await cur.fetchone()
    return row[0] if row else 0


async def _set_user_version(db, version: int):
    await db.execute(f"PRAGMA user_version = {int(version)}")


class Database:

    @staticmethod
    async def init():
        db = await get_db()
        version = await _get_user_version(db)

        if version < 1:
            await db.executescript(_SCHEMA_V1)
            await _set_user_version(db, 1)
            await db.commit()
            version = 1

        if version < 2:
            await db.executescript(_SCHEMA_V2)
            await _set_user_version(db, 2)
            await db.commit()
            version = 2

        if version < 3:
            await db.executescript(_SCHEMA_V3)
            await _seed_categories(db)
            await _set_user_version(db, 3)
            await db.commit()
            version = 3

        if version < 4:
            await db.executescript(_SCHEMA_V4)
            await _set_user_version(db, 4)
            await db.commit()
            version = 4

        if version < 5:
            await db.executescript(_SCHEMA_V5)
            await _set_user_version(db, 5)
            await db.commit()


_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id           INTEGER UNIQUE NOT NULL,
    ghost_id        TEXT UNIQUE NOT NULL,
    referrer_id     INTEGER REFERENCES users(id),
    balance         INTEGER NOT NULL DEFAULT 0,
    pending_balance INTEGER NOT NULL DEFAULT 0,
    total_earned    INTEGER NOT NULL DEFAULT 0,
    is_banned       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS listings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id   INTEGER NOT NULL REFERENCES users(id),
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    price       INTEGER NOT NULL,
    category    TEXT NOT NULL DEFAULT 'other',
    file_id     TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id          INTEGER NOT NULL REFERENCES listings(id),
    buyer_id            INTEGER NOT NULL REFERENCES users(id),
    seller_id           INTEGER NOT NULL REFERENCES users(id),
    amount              INTEGER NOT NULL,
    fee                 INTEGER NOT NULL,
    referral_fee        INTEGER NOT NULL DEFAULT 0,
    net_to_seller       INTEGER NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending_payment',
    funds_released      INTEGER NOT NULL DEFAULT 0,
    crypto_invoice_id   TEXT UNIQUE,
    crypto_pay_url      TEXT,
    delivery_note       TEXT,
    dispute_reason      TEXT,
    auto_confirm_at     TEXT,
    confirmed_at        TEXT,
    payout_available_at TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    order_id    INTEGER REFERENCES orders(id),
    type        TEXT NOT NULL,
    amount      INTEGER NOT NULL,
    comment     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS withdrawals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    amount      INTEGER NOT NULL,
    wallet      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    admin_note  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS disputes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER UNIQUE NOT NULL REFERENCES orders(id),
    opened_by   INTEGER NOT NULL REFERENCES users(id),
    reason      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open',
    admin_note  TEXT,
    resolved_by INTEGER REFERENCES users(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_orders_buyer        ON orders(buyer_id);
CREATE INDEX IF NOT EXISTS idx_orders_seller       ON orders(seller_id);
CREATE INDEX IF NOT EXISTS idx_orders_status       ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_invoice      ON orders(crypto_invoice_id);
CREATE INDEX IF NOT EXISTS idx_orders_auto         ON orders(auto_confirm_at) WHERE status='delivered';
CREATE INDEX IF NOT EXISTS idx_orders_payout       ON orders(payout_available_at) WHERE status='confirmed' AND funds_released=1;
CREATE INDEX IF NOT EXISTS idx_orders_pending_pair ON orders(buyer_id, listing_id, status);
CREATE INDEX IF NOT EXISTS idx_listings_seller     ON listings(seller_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user   ON transactions(user_id);
"""

_SCHEMA_V2 = """
-- Отзывы
-- Один отзыв на сделку. Только покупатель → продавец.
CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER UNIQUE NOT NULL REFERENCES orders(id),
    reviewer_id INTEGER NOT NULL REFERENCES users(id),
    target_id   INTEGER NOT NULL REFERENCES users(id),
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    text        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reviews_target ON reviews(target_id);
CREATE INDEX IF NOT EXISTS idx_listings_active_created ON listings(is_active, created_at);
"""

_SCHEMA_V3 = """
-- Динамические категории и подкатегории.
-- parent_id NULL = корневая категория ("Игры", "Telegram", "Соцсети")
-- parent_id != NULL = подкатегория ("Brawl Stars" внутри "Игры")
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id   INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    emoji       TEXT NOT NULL DEFAULT '🔖',
    sort_order  INTEGER NOT NULL DEFAULT 100,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id, is_active, sort_order);

-- Предложения новых категорий от пользователей
CREATE TABLE IF NOT EXISTS category_suggestions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    suggested   TEXT NOT NULL,
    parent_hint TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    -- pending | approved | rejected
    admin_note  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_suggestions_status ON category_suggestions(status);

-- Привязка листинга к категории через id (старая колонка category остаётся для совместимости)
ALTER TABLE listings ADD COLUMN category_id INTEGER REFERENCES categories(id);
CREATE INDEX IF NOT EXISTS idx_listings_category ON listings(category_id, is_active);
"""


async def _seed_categories(db):
    """Стартовый набор категорий и подкатегорий."""
    seed = [
        # (parent_name_or_None, name, emoji, sort)
        (None, "Telegram", "✈️", 10),
        (None, "Игры", "🎮", 20),
        (None, "Соцсети", "📱", 30),
        (None, "Стриминг", "🎬", 40),
        (None, "Криптовалюты", "₿", 50),
        (None, "Файлы и софт", "📁", 60),
        (None, "Консультации", "💬", 70),
        (None, "Другое", "🔖", 999),
    ]
    parent_ids = {}
    for _, name, emoji, sort in seed:
        cur = await db.execute(
            "INSERT INTO categories (parent_id, name, emoji, sort_order) VALUES (NULL, ?, ?, ?)",
            (name, emoji, sort),
        )
        parent_ids[name] = cur.lastrowid

    # Подкатегории
    sub = [
        # parent_name, name, emoji
        ("Telegram", "Premium подписки", "⭐"),
        ("Telegram", "Stars", "✨"),
        ("Telegram", "Юзернеймы", "🆔"),
        ("Telegram", "Каналы и группы", "📢"),

        ("Игры", "Brawl Stars", "💥"),
        ("Игры", "Standoff 2", "🔫"),
        ("Игры", "Clash Royale", "👑"),
        ("Игры", "Clash of Clans", "🏰"),
        ("Игры", "PUBG Mobile", "🪖"),
        ("Игры", "Mobile Legends", "🗡"),
        ("Игры", "Genshin Impact", "🌸"),
        ("Игры", "Roblox", "🟥"),
        ("Игры", "Minecraft", "⛏"),
        ("Игры", "Fortnite", "🌀"),
        ("Игры", "Valorant", "🎯"),
        ("Игры", "CS2 / CS:GO", "🔪"),
        ("Игры", "Dota 2", "🛡"),
        ("Игры", "World of Tanks", "🚜"),
        ("Игры", "GTA Online", "🚗"),

        ("Соцсети", "Instagram", "📷"),
        ("Соцсети", "TikTok", "🎵"),
        ("Соцсети", "YouTube", "▶️"),
        ("Соцсети", "Twitter / X", "🐦"),
        ("Соцсети", "Discord", "💬"),

        ("Стриминг", "Spotify", "🎧"),
        ("Стриминг", "Netflix", "🎞"),
        ("Стриминг", "YouTube Premium", "🔴"),

        ("Криптовалюты", "USDT", "💵"),
        ("Криптовалюты", "BTC", "🟠"),
        ("Криптовалюты", "TON", "💎"),

        ("Файлы и софт", "Лицензии и ключи", "🔑"),
        ("Файлы и софт", "VPN", "🛡"),
        ("Файлы и софт", "Базы данных", "🗄"),

        ("Консультации", "IT и разработка", "💻"),
        ("Консультации", "Маркетинг", "📈"),
        ("Консультации", "Юридические", "⚖️"),
    ]
    for parent_name, name, emoji in sub:
        parent_id = parent_ids[parent_name]
        await db.execute(
            "INSERT INTO categories (parent_id, name, emoji, sort_order) VALUES (?, ?, ?, 100)",
            (parent_id, name, emoji),
        )


_SCHEMA_V4 = """
ALTER TABLE users ADD COLUMN lang TEXT NOT NULL DEFAULT 'en';
"""


_SCHEMA_V5 = """
-- ─────────────────────────────────────────────────────────────────────────────
-- Анонимный чат внутри сделки
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deal_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id),
    sender_id   INTEGER NOT NULL REFERENCES users(id),
    -- role: 'buyer' | 'seller'
    role        TEXT NOT NULL,
    text        TEXT,
    file_id     TEXT,
    file_type   TEXT,
    -- 'text' | 'document' | 'photo' | 'video' | 'audio'
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_dm_order ON deal_messages(order_id, created_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- Подписки на категории
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS category_subscriptions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, category_id)
);
CREATE INDEX IF NOT EXISTS idx_cat_sub ON category_subscriptions(category_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- Буст объявлений
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS listing_boosts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id  INTEGER NOT NULL REFERENCES listings(id),
    user_id     INTEGER NOT NULL REFERENCES users(id),
    amount_paid INTEGER NOT NULL,
    -- длительность в часах
    hours       INTEGER NOT NULL DEFAULT 24,
    expires_at  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_boost_listing ON listing_boosts(listing_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_boost_active  ON listing_boosts(expires_at) WHERE expires_at > datetime('now');

-- ─────────────────────────────────────────────────────────────────────────────
-- Промокоды
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS promo_codes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT UNIQUE NOT NULL,
    discount_pct    INTEGER NOT NULL DEFAULT 0,
    -- скидка на комиссию платформы в %
    max_uses        INTEGER NOT NULL DEFAULT 1,
    used_count      INTEGER NOT NULL DEFAULT 0,
    expires_at      TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS promo_uses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    promo_id    INTEGER NOT NULL REFERENCES promo_codes(id),
    user_id     INTEGER NOT NULL REFERENCES users(id),
    order_id    INTEGER REFERENCES orders(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(promo_id, user_id)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Новые поля через ALTER TABLE
-- ─────────────────────────────────────────────────────────────────────────────

-- Счётчик завершённых сделок (продавец)
ALTER TABLE users ADD COLUMN completed_sales INTEGER NOT NULL DEFAULT 0;
-- Дата первой сделки (для cooldown вывода)
ALTER TABLE users ADD COLUMN first_deal_at TEXT;

-- Флаг «чат открыт» для ордера
ALTER TABLE orders ADD COLUMN chat_enabled INTEGER NOT NULL DEFAULT 0;
-- Флаг «покупатель подтвердил условия» (гарантийный период)
ALTER TABLE orders ADD COLUMN buyer_confirmed_terms INTEGER NOT NULL DEFAULT 0;
-- Применённый промокод
ALTER TABLE orders ADD COLUMN promo_id INTEGER REFERENCES promo_codes(id);

-- Буст-флаг на листинге (кэш)
ALTER TABLE listings ADD COLUMN is_boosted INTEGER NOT NULL DEFAULT 0;
ALTER TABLE listings ADD COLUMN boost_expires_at TEXT;
"""
