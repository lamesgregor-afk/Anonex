import secrets
import string
from typing import Optional
from database.db import get_db, transaction

_GHOST_ALPHABET = string.ascii_lowercase + string.digits
_GHOST_LEN = 7


def _gen_ghost_id() -> str:
    suffix = "".join(secrets.choice(_GHOST_ALPHABET) for _ in range(_GHOST_LEN))
    return f"ghost_{suffix}"


class UserService:

    @staticmethod
    async def get_or_create(tg_id: int, referrer_ghost_id: Optional[str] = None) -> dict:
        db = await get_db()

        async with db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)) as cur:
            row = await cur.fetchone()
        if row:
            return dict(row)

        referrer_id = None
        if referrer_ghost_id:
            async with db.execute(
                "SELECT id FROM users WHERE ghost_id = ?", (referrer_ghost_id,)
            ) as cur:
                ref_row = await cur.fetchone()
            if ref_row:
                referrer_id = ref_row["id"]

        ghost_id = _gen_ghost_id()
        for _ in range(15):
            async with db.execute(
                "SELECT 1 FROM users WHERE ghost_id = ?", (ghost_id,)
            ) as cur:
                if not await cur.fetchone():
                    break
            ghost_id = _gen_ghost_id()

        await db.execute(
            "INSERT INTO users (tg_id, ghost_id, referrer_id) VALUES (?, ?, ?)",
            (tg_id, ghost_id, referrer_id),
        )
        await db.commit()

        async with db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)) as cur:
            row = await cur.fetchone()
        return dict(row)

    @staticmethod
    async def get_by_tg_id(tg_id: int) -> Optional[dict]:
        db = await get_db()
        async with db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    async def get_by_id(user_id: int) -> Optional[dict]:
        db = await get_db()
        async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    async def get_by_ghost_id(ghost_id: str) -> Optional[dict]:
        db = await get_db()
        async with db.execute("SELECT * FROM users WHERE ghost_id = ?", (ghost_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    async def add_balance(user_id: int, amount_micro: int):
        """Просто начислить (refund, ручной adjust). НЕ изменяет total_earned."""
        db = await get_db()
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (amount_micro, user_id),
        )
        await db.commit()

    @staticmethod
    async def add_earned_balance(user_id: int, amount_micro: int):
        """Начислить заработок (реферальные) — попадает в total_earned."""
        db = await get_db()
        await db.execute(
            """UPDATE users
               SET balance = balance + ?,
                   total_earned = total_earned + ?
               WHERE id = ?""",
            (amount_micro, amount_micro, user_id),
        )
        await db.commit()

    @staticmethod
    async def add_pending(user_id: int, amount_micro: int):
        db = await get_db()
        await db.execute(
            "UPDATE users SET pending_balance = pending_balance + ? WHERE id = ?",
            (amount_micro, user_id),
        )
        await db.commit()

    @staticmethod
    async def move_pending_to_balance(user_id: int, amount_micro: int) -> bool:
        """Атомарно: pending → balance + total_earned. True если успешно."""
        db = await get_db()
        cur = await db.execute(
            """UPDATE users
               SET balance = balance + ?,
                   pending_balance = pending_balance - ?,
                   total_earned = total_earned + ?
               WHERE id = ? AND pending_balance >= ?""",
            (amount_micro, amount_micro, amount_micro, user_id, amount_micro),
        )
        await db.commit()
        return cur.rowcount > 0

    @staticmethod
    async def deduct_balance(user_id: int, amount_micro: int) -> bool:
        """Атомарное списание с проверкой достаточности средств."""
        db = await get_db()
        cur = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?",
            (amount_micro, user_id, amount_micro),
        )
        await db.commit()
        return cur.rowcount > 0

    @staticmethod
    async def get_referrer(user_id: int) -> Optional[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT u2.* FROM users u1
               JOIN users u2 ON u1.referrer_id = u2.id
               WHERE u1.id = ?""",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    async def count_referrals(user_id: int) -> int:
        db = await get_db()
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE referrer_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        return row["cnt"] if row else 0
