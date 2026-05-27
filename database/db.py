"""
database/db.py

Изменения:
- Добавлен async-context `transaction()` для атомарных мульти-стейтментов
- Колонка orders.funds_released — флаг "деньги в pending у продавца уже начислены"
  → release_funds становится идемпотентной, защищена от частичных сбоев
- Простая система миграций через user_version PRAGMA
- DB_PATH читается из env DB_PATH (для Railway volume)
"""
import os
import aiosqlite
import asyncio
import contextlib
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "ghostmarket.db")

_db: Optional[aiosqlite.Connection] = None
_db_lock = asyncio.Lock()
_write_lock = asyncio.Lock()  # сериализуем write-операции (SQLite single-writer)


def to_micro(usdt: float) -> int:
    """USDT → микро-USDT (int) через Decimal — без float-погрешностей."""
    from decimal import Decimal, ROUND_HALF_UP
    return int(
        Decimal(str(usdt)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        * 1_000_000
    )


def fmt(micro: int, decimals: int = 4) -> str:
    """Микро-USDT → строка для UI: '1.2345'."""
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
    """
    Атомарная транзакция. Используется для связки операций,
    которые должны выполниться вместе или не выполниться вообще.

    Пример:
        async with transaction() as db:
            await db.execute("UPDATE ... ")
            await db.execute("INSERT ...")
        # commit / rollback автоматически
    """
    db = await get_db()
    async with _write_lock:
        try:
            await db.execute("BEGIN IMMEDIATE")
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise


# ─── Миграции ───────────────────────────────────────────────────────────────

CURRENT_VERSION = 1


async def _get_user_version(db) -> int:
    async with db.execute("PRAGMA user_version") as cur:
        row = await cur.fetchone()
    return row[0] if row else 0


async def _set_user_version(db, version: int):
    # PRAGMA не принимает параметры — но version это int, безопасно через f-string
    await db.execute(f"PRAGMA user_version = {int(version)}")


# ─── Schema bootstrap ────────────────────────────────────────────────────────

class Database:

    @staticmethod
    async def init():
        db = await get_db()
        version = await _get_user_version(db)

        if version < 1:
            await db.executescript(_SCHEMA_V1)
            await _set_user_version(db, 1)
            await db.commit()


_SCHEMA_V1 = """
-- Пользователи
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

-- Объявления
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

-- Заказы
-- funds_released: 0 — деньги ещё не разнесены продавцу/рефереру; 1 — разнесены
--                 защищает от частичной выплаты при крэше между UPDATE status и release_funds
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

-- Транзакции
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    order_id    INTEGER REFERENCES orders(id),
    type        TEXT NOT NULL,
    amount      INTEGER NOT NULL,
    comment     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Заявки на вывод
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

-- Споры
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
