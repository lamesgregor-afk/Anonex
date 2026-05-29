"""
chat_service.py — анонимный чат внутри сделки.

Сообщения хранятся в deal_messages.
Бот проксирует: покупатель пишет → продавец получает (и наоборот).
Реальные tg_id скрыты — только role (buyer/seller).
"""
from typing import Optional, List
from database.db import get_db


class ChatService:

    @staticmethod
    async def save_message(
        order_id: int,
        sender_id: int,
        role: str,
        text: Optional[str] = None,
        file_id: Optional[str] = None,
        file_type: Optional[str] = None,
    ) -> dict:
        db = await get_db()
        async with db.execute(
            """INSERT INTO deal_messages
               (order_id, sender_id, role, text, file_id, file_type)
               VALUES (?, ?, ?, ?, ?, ?) RETURNING *""",
            (order_id, sender_id, role, text, file_id, file_type),
        ) as cur:
            row = await cur.fetchone()
        await db.commit()
        return dict(row)

    @staticmethod
    async def get_history(order_id: int, limit: int = 50) -> List[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT * FROM deal_messages
               WHERE order_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (order_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in reversed(rows)]

    @staticmethod
    async def enable_chat(order_id: int):
        db = await get_db()
        await db.execute(
            "UPDATE orders SET chat_enabled = 1 WHERE id = ?", (order_id,)
        )
        await db.commit()

    @staticmethod
    async def is_chat_enabled(order_id: int) -> bool:
        db = await get_db()
        async with db.execute(
            "SELECT chat_enabled FROM orders WHERE id = ?", (order_id,)
        ) as cur:
            row = await cur.fetchone()
        return bool(row and row["chat_enabled"])
