from typing import Optional, List
from database.db import get_db, to_micro

CATEGORIES = ["file", "service", "consultation", "other"]
CATEGORY_EMOJI = {"file": "📁", "service": "🛠", "consultation": "💬", "other": "🔖"}


class ListingService:

    @staticmethod
    async def create(
        seller_id: int,
        title: str,
        description: str,
        price_usdt: float,
        category: str = "other",
        file_id: Optional[str] = None,
    ) -> dict:
        price_micro = to_micro(price_usdt)
        db = await get_db()
        async with db.execute(
            """INSERT INTO listings (seller_id, title, description, price, category, file_id)
               VALUES (?, ?, ?, ?, ?, ?) RETURNING *""",
            (seller_id, title, description, price_micro, category, file_id),
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
        db = await get_db()
        cur = await db.execute(
            "UPDATE listings SET is_active = 0 WHERE id = ? AND seller_id = ?",
            (listing_id, seller_id),
        )
        await db.commit()
        return cur.rowcount > 0
