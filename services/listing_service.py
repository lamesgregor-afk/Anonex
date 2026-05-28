from typing import Optional, List
from database.db import get_db, to_micro

CATEGORIES = ["file", "service", "consultation", "other"]
CATEGORY_EMOJI = {"file": "📁", "service": "🛠", "consultation": "💬", "other": "🔖"}

LISTING_LIFETIME_DAYS = 30


class ListingService:

    @staticmethod
    async def create(
        seller_id: int,
        title: str,
        description: str,
        price_usdt: float,
        category: str = "other",
        category_id: Optional[int] = None,
        file_id: Optional[str] = None,
    ) -> dict:
        price_micro = to_micro(price_usdt)
        db = await get_db()
        async with db.execute(
            """INSERT INTO listings
                (seller_id, title, description, price, category, category_id, file_id)
               VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING *""",
            (seller_id, title, description, price_micro, category, category_id, file_id),
        ) as cur:
            row = await cur.fetchone()
        await db.commit()
        return dict(row)

    @staticmethod
    async def get_by_id(listing_id: int) -> Optional[dict]:
        db = await get_db()
        async with db.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    async def get_by_seller(seller_id: int, limit: int = 50) -> List[dict]:
        db = await get_db()
        async with db.execute(
            "SELECT * FROM listings WHERE seller_id = ? ORDER BY created_at DESC LIMIT ?",
            (seller_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def deactivate(listing_id: int, seller_id: int) -> bool:
        """Снять с продажи (только владельцем)."""
        db = await get_db()
        cur = await db.execute(
            "UPDATE listings SET is_active = 0 WHERE id = ? AND seller_id = ?",
            (listing_id, seller_id),
        )
        await db.commit()
        return cur.rowcount > 0

    @staticmethod
    async def admin_deactivate(listing_id: int) -> bool:
        """Админ-снятие с продажи (без проверки владельца)."""
        db = await get_db()
        cur = await db.execute(
            "UPDATE listings SET is_active = 0 WHERE id = ?",
            (listing_id,),
        )
        await db.commit()
        return cur.rowcount > 0

    @staticmethod
    async def expire_old(days: int = LISTING_LIFETIME_DAYS) -> int:
        """
        Деактивирует объявления старше N дней.
        Возвращает количество затронутых.
        """
        db = await get_db()
        cur = await db.execute(
            f"""UPDATE listings SET is_active = 0
                WHERE is_active = 1
                AND created_at <= datetime('now', '-{int(days)} days')""",
        )
        await db.commit()
        return cur.rowcount

    @staticmethod
    async def search(query: str, limit: int = 20) -> List[dict]:
        """Простой поиск по title/description (LIKE)."""
        db = await get_db()
        like = f"%{query}%"
        async with db.execute(
            """SELECT l.*, u.ghost_id as seller_ghost
               FROM listings l JOIN users u ON l.seller_id = u.id
               WHERE l.is_active = 1
               AND (l.title LIKE ? OR l.description LIKE ?)
               ORDER BY l.created_at DESC LIMIT ?""",
            (like, like, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
