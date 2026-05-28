from typing import Optional, List
from database.db import get_db


class ReviewService:

    @staticmethod
    async def create(
        order_id: int,
        reviewer_id: int,
        target_id: int,
        rating: int,
        text: Optional[str] = None,
    ) -> Optional[dict]:
        """Создаёт отзыв. UNIQUE по order_id — повторно нельзя."""
        if rating < 1 or rating > 5:
            return None
        db = await get_db()
        try:
            async with db.execute(
                """INSERT INTO reviews (order_id, reviewer_id, target_id, rating, text)
                   VALUES (?, ?, ?, ?, ?) RETURNING *""",
                (order_id, reviewer_id, target_id, rating, (text or "").strip()[:500] or None),
            ) as cur:
                row = await cur.fetchone()
            await db.commit()
            return dict(row) if row else None
        except Exception:
            return None

    @staticmethod
    async def get_for_order(order_id: int) -> Optional[dict]:
        db = await get_db()
        async with db.execute(
            "SELECT * FROM reviews WHERE order_id = ?", (order_id,)
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    async def get_user_summary(user_id: int) -> dict:
        """Средняя оценка и количество отзывов о пользователе."""
        db = await get_db()
        async with db.execute(
            """SELECT COUNT(*) as cnt, COALESCE(AVG(rating), 0) as avg_rating
               FROM reviews WHERE target_id = ?""",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        return {
            "count": row["cnt"] if row else 0,
            "avg": round(row["avg_rating"], 2) if row else 0.0,
        }

    @staticmethod
    async def get_user_reviews(user_id: int, limit: int = 10) -> List[dict]:
        """Последние отзывы о пользователе вместе с ghost-id автора."""
        db = await get_db()
        async with db.execute(
            """SELECT r.*, u.ghost_id as reviewer_ghost
               FROM reviews r
               JOIN users u ON r.reviewer_id = u.id
               WHERE r.target_id = ?
               ORDER BY r.created_at DESC LIMIT ?""",
            (user_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
