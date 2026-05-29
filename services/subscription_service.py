"""
subscription_service.py — подписки на категории.
Юзер подписывается → при появлении нового листинга получает уведомление.
"""
from typing import List
from database.db import get_db


class SubscriptionService:

    @staticmethod
    async def subscribe(user_id: int, category_id: int) -> bool:
        """True если подписка создана, False если уже была."""
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO category_subscriptions (user_id, category_id) VALUES (?, ?)",
                (user_id, category_id),
            )
            await db.commit()
            return True
        except Exception:
            return False

    @staticmethod
    async def unsubscribe(user_id: int, category_id: int) -> bool:
        db = await get_db()
        cur = await db.execute(
            "DELETE FROM category_subscriptions WHERE user_id = ? AND category_id = ?",
            (user_id, category_id),
        )
        await db.commit()
        return cur.rowcount > 0

    @staticmethod
    async def is_subscribed(user_id: int, category_id: int) -> bool:
        db = await get_db()
        async with db.execute(
            "SELECT 1 FROM category_subscriptions WHERE user_id = ? AND category_id = ?",
            (user_id, category_id),
        ) as cur:
            return await cur.fetchone() is not None

    @staticmethod
    async def get_user_subscriptions(user_id: int) -> List[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT cs.*, c.name, c.emoji
               FROM category_subscriptions cs
               JOIN categories c ON cs.category_id = c.id
               WHERE cs.user_id = ?""",
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def get_subscribers(category_id: int) -> List[int]:
        """Возвращает список user_id подписчиков категории и всех её родителей."""
        db = await get_db()
        # Подписчики самой категории + подписчики родительской категории
        async with db.execute(
            """SELECT DISTINCT cs.user_id
               FROM category_subscriptions cs
               WHERE cs.category_id = ?
               OR cs.category_id = (
                   SELECT parent_id FROM categories WHERE id = ?
               )""",
            (category_id, category_id),
        ) as cur:
            rows = await cur.fetchall()
        return [r["user_id"] for r in rows]

    @staticmethod
    async def get_subscriber_tg_ids(category_id: int) -> List[int]:
        """Возвращает tg_id подписчиков (для отправки уведомлений)."""
        db = await get_db()
        async with db.execute(
            """SELECT DISTINCT u.tg_id
               FROM category_subscriptions cs
               JOIN users u ON cs.user_id = u.id
               WHERE cs.category_id = ?
               OR cs.category_id = (
                   SELECT parent_id FROM categories WHERE id = ?
               )""",
            (category_id, category_id),
        ) as cur:
            rows = await cur.fetchall()
        return [r["tg_id"] for r in rows]
