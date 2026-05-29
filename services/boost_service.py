"""
boost_service.py — платный буст объявлений.

Тарифы:
  24ч → 1 USDT
  72ч → 2.5 USDT
  168ч (7д) → 5 USDT

Бустнутые объявления показываются первыми в маркете.
"""
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from database.db import get_db, to_micro

BOOST_PLANS = [
    {"hours": 24,  "price_usdt": 1.0,  "label": "24h — 1 USDT"},
    {"hours": 72,  "price_usdt": 2.5,  "label": "72h — 2.5 USDT"},
    {"hours": 168, "price_usdt": 5.0,  "label": "7 days — 5 USDT"},
]


class BoostService:

    @staticmethod
    async def apply_boost(
        listing_id: int,
        user_id: int,
        hours: int,
        price_usdt: float,
    ) -> bool:
        """
        Списывает с баланса и активирует буст.
        Если буст уже активен — продлевает от текущего expires_at.
        """
        amount_micro = to_micro(price_usdt)
        db = await get_db()

        # Атомарное списание
        cur = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?",
            (amount_micro, user_id, amount_micro),
        )
        if cur.rowcount == 0:
            await db.commit()
            return False

        # Вычисляем expires_at (продлеваем если уже есть активный)
        async with db.execute(
            "SELECT boost_expires_at FROM listings WHERE id = ?", (listing_id,)
        ) as c:
            row = await c.fetchone()

        now = datetime.now(timezone.utc)
        if row and row["boost_expires_at"]:
            try:
                current_exp = datetime.fromisoformat(row["boost_expires_at"])
                if current_exp.tzinfo is None:
                    current_exp = current_exp.replace(tzinfo=timezone.utc)
                base = max(now, current_exp)
            except Exception:
                base = now
        else:
            base = now

        expires_at = (base + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

        await db.execute(
            """UPDATE listings
               SET is_boosted = 1, boost_expires_at = ?
               WHERE id = ?""",
            (expires_at, listing_id),
        )
        await db.execute(
            """INSERT INTO listing_boosts (listing_id, user_id, amount_paid, hours, expires_at)
               VALUES (?, ?, ?, ?, ?)""",
            (listing_id, user_id, amount_micro, hours, expires_at),
        )
        await db.commit()
        return True

    @staticmethod
    async def expire_boosts():
        """Снимает флаг is_boosted с истёкших бустов. Вызывается планировщиком."""
        db = await get_db()
        cur = await db.execute(
            """UPDATE listings
               SET is_boosted = 0, boost_expires_at = NULL
               WHERE is_boosted = 1
               AND boost_expires_at <= datetime('now')"""
        )
        await db.commit()
        return cur.rowcount

    @staticmethod
    async def get_active_boost(listing_id: int) -> Optional[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT * FROM listing_boosts
               WHERE listing_id = ? AND expires_at > datetime('now')
               ORDER BY expires_at DESC LIMIT 1""",
            (listing_id,),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None
