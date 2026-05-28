"""
category_service.py — динамические категории и подкатегории + предложения от юзеров.
"""
from typing import Optional, List
from database.db import get_db


class CategoryService:

    @staticmethod
    async def get_roots() -> List[dict]:
        """Корневые категории (без parent_id)."""
        db = await get_db()
        async with db.execute(
            """SELECT * FROM categories
               WHERE parent_id IS NULL AND is_active = 1
               ORDER BY sort_order, name"""
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def get_children(parent_id: int) -> List[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT * FROM categories
               WHERE parent_id = ? AND is_active = 1
               ORDER BY sort_order, name""",
            (parent_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def get_by_id(category_id: int) -> Optional[dict]:
        db = await get_db()
        async with db.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    async def get_path(category_id: int) -> List[dict]:
        """Возвращает [parent, child] или [root]. Для отображения «Игры → Brawl Stars»."""
        cat = await CategoryService.get_by_id(category_id)
        if not cat:
            return []
        if cat["parent_id"]:
            parent = await CategoryService.get_by_id(cat["parent_id"])
            if parent:
                return [parent, cat]
        return [cat]

    @staticmethod
    async def has_children(category_id: int) -> bool:
        db = await get_db()
        async with db.execute(
            "SELECT 1 FROM categories WHERE parent_id = ? AND is_active = 1 LIMIT 1",
            (category_id,),
        ) as cur:
            return await cur.fetchone() is not None

    @staticmethod
    async def create(
        name: str,
        emoji: str = "🔖",
        parent_id: Optional[int] = None,
        sort_order: int = 100,
    ) -> dict:
        db = await get_db()
        async with db.execute(
            """INSERT INTO categories (parent_id, name, emoji, sort_order)
               VALUES (?, ?, ?, ?) RETURNING *""",
            (parent_id, name.strip()[:60], emoji[:8], sort_order),
        ) as cur:
            row = await cur.fetchone()
        await db.commit()
        return dict(row)

    @staticmethod
    async def rename(category_id: int, new_name: str, new_emoji: Optional[str] = None) -> bool:
        db = await get_db()
        if new_emoji:
            cur = await db.execute(
                "UPDATE categories SET name = ?, emoji = ? WHERE id = ?",
                (new_name.strip()[:60], new_emoji[:8], category_id),
            )
        else:
            cur = await db.execute(
                "UPDATE categories SET name = ? WHERE id = ?",
                (new_name.strip()[:60], category_id),
            )
        await db.commit()
        return cur.rowcount > 0

    @staticmethod
    async def deactivate(category_id: int) -> bool:
        db = await get_db()
        cur = await db.execute(
            "UPDATE categories SET is_active = 0 WHERE id = ?", (category_id,)
        )
        await db.commit()
        return cur.rowcount > 0

    # ─── Предложения категорий ────────────────────────────────────────────────

    @staticmethod
    async def suggest(user_id: int, name: str, parent_hint: Optional[str] = None) -> dict:
        db = await get_db()
        async with db.execute(
            """INSERT INTO category_suggestions (user_id, suggested, parent_hint)
               VALUES (?, ?, ?) RETURNING *""",
            (user_id, name.strip()[:100], (parent_hint or "").strip()[:100] or None),
        ) as cur:
            row = await cur.fetchone()
        await db.commit()
        return dict(row)

    @staticmethod
    async def get_pending_suggestions(limit: int = 20) -> List[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT s.*, u.ghost_id
               FROM category_suggestions s
               JOIN users u ON s.user_id = u.id
               WHERE s.status = 'pending'
               ORDER BY s.created_at ASC LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def get_suggestion(suggestion_id: int) -> Optional[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT s.*, u.ghost_id, u.tg_id
               FROM category_suggestions s
               JOIN users u ON s.user_id = u.id
               WHERE s.id = ?""",
            (suggestion_id,),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    async def update_suggestion_status(
        suggestion_id: int, status: str, admin_note: str = ""
    ) -> bool:
        if status not in ("approved", "rejected"):
            return False
        db = await get_db()
        cur = await db.execute(
            """UPDATE category_suggestions
               SET status = ?, admin_note = ?, updated_at = datetime('now')
               WHERE id = ? AND status = 'pending'""",
            (status, admin_note, suggestion_id),
        )
        await db.commit()
        return cur.rowcount > 0

    @staticmethod
    async def count_listings(category_id: int) -> int:
        """Сколько активных листингов в категории (включая подкатегории если она root)."""
        db = await get_db()
        async with db.execute(
            """SELECT COUNT(*) as cnt FROM listings l
               WHERE l.is_active = 1
               AND (l.category_id = ? OR l.category_id IN (
                   SELECT id FROM categories WHERE parent_id = ?
               ))""",
            (category_id, category_id),
        ) as cur:
            row = await cur.fetchone()
        return row["cnt"] if row else 0
