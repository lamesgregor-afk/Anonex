"""
admin_service.py

Фикс resolve_dispute:
- resolved_seller теперь ставит status='confirmed' + payout_available_at
  (раньше выставлял confirmed без payout_available_at → деньги застревали в pending)
- Всё в одной транзакции
"""
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from database.db import get_db, transaction
from config import settings
import logging

logger = logging.getLogger(__name__)


def _utc_iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).strftime("%Y-%m-%d %H:%M:%S")


class AdminService:

    @staticmethod
    async def get_open_disputes() -> List[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT d.*, o.amount, o.status as order_status,
                      ub.ghost_id as buyer_ghost, us.ghost_id as seller_ghost
               FROM disputes d
               JOIN orders o ON d.order_id = o.id
               JOIN users ub ON o.buyer_id = ub.id
               JOIN users us ON o.seller_id = us.id
               WHERE d.status = 'open'
               ORDER BY d.created_at ASC"""
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def resolve_dispute(
        dispute_id: int,
        resolution: str,  # 'resolved_buyer' | 'resolved_seller'
        admin_id: int,
        admin_note: str = "",
    ) -> Optional[dict]:
        """
        Атомарно: закрывает спор + меняет статус ордера + (для продавца) выставляет
        payout_available_at, чтобы scheduler корректно разморозил pending.
        """
        if resolution not in ("resolved_buyer", "resolved_seller"):
            return None

        try:
            async with transaction() as db:
                async with db.execute(
                    "SELECT * FROM disputes WHERE id = ? AND status = 'open'",
                    (dispute_id,),
                ) as cur:
                    dispute = await cur.fetchone()
                if not dispute:
                    raise _NoOpRollback()

                cur = await db.execute(
                    """UPDATE disputes
                       SET status = ?, admin_note = ?, resolved_by = ?, updated_at = datetime('now')
                       WHERE id = ? AND status = 'open'""",
                    (resolution, admin_note, admin_id, dispute_id),
                )
                if cur.rowcount == 0:
                    raise _NoOpRollback()

                if resolution == "resolved_buyer":
                    await db.execute(
                        """UPDATE orders
                           SET status = 'refunded', updated_at = datetime('now')
                           WHERE id = ? AND status = 'disputed'""",
                        (dispute["order_id"],),
                    )
                else:
                    # resolved_seller — confirmed + payout_available_at
                    payout_at = _utc_iso(timedelta(days=settings.WITHDRAWAL_HOLD_DAYS))
                    await db.execute(
                        """UPDATE orders
                           SET status = 'confirmed',
                               confirmed_at = datetime('now'),
                               payout_available_at = ?,
                               updated_at = datetime('now')
                           WHERE id = ? AND status = 'disputed'""",
                        (payout_at, dispute["order_id"]),
                    )

                logger.info(
                    "[admin] Dispute #%d resolved as %s by admin %d",
                    dispute_id, resolution, admin_id,
                )
                return dict(dispute)
        except _NoOpRollback:
            return None

    @staticmethod
    async def get_recent_transactions(limit: int = 50) -> List[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT t.*, u.ghost_id
               FROM transactions t
               JOIN users u ON t.user_id = u.id
               ORDER BY t.created_at DESC LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def get_pending_withdrawals() -> List[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT w.*, u.ghost_id, u.tg_id
               FROM withdrawals w
               JOIN users u ON w.user_id = u.id
               WHERE w.status = 'pending'
               ORDER BY w.created_at ASC"""
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def get_withdrawal(withdrawal_id: int) -> Optional[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT w.*, u.ghost_id, u.tg_id
               FROM withdrawals w JOIN users u ON w.user_id = u.id
               WHERE w.id = ?""",
            (withdrawal_id,),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    async def claim_withdrawal_for_processing(withdrawal_id: int) -> bool:
        """
        Атомарно: pending → processing. Только админ-инициатор сможет переводить дальше.
        Защита от двойного клика «Одобрить».
        """
        db = await get_db()
        cur = await db.execute(
            """UPDATE withdrawals
               SET status = 'processing', updated_at = datetime('now')
               WHERE id = ? AND status = 'pending'""",
            (withdrawal_id,),
        )
        await db.commit()
        return cur.rowcount > 0

    @staticmethod
    async def finalize_withdrawal(withdrawal_id: int, status: str, admin_note: str = "") -> bool:
        """processing → done | rejected. Используется после CryptoBot transfer."""
        if status not in ("done", "rejected"):
            return False
        db = await get_db()
        cur = await db.execute(
            """UPDATE withdrawals
               SET status = ?, admin_note = ?, updated_at = datetime('now')
               WHERE id = ? AND status = 'processing'""",
            (status, admin_note, withdrawal_id),
        )
        await db.commit()
        return cur.rowcount > 0

    @staticmethod
    async def reject_pending_withdrawal(withdrawal_id: int, admin_note: str = "") -> bool:
        """Отклонить pending без processing-стадии (отказ до отправки)."""
        db = await get_db()
        cur = await db.execute(
            """UPDATE withdrawals
               SET status = 'rejected', admin_note = ?, updated_at = datetime('now')
               WHERE id = ? AND status = 'pending'""",
            (admin_note, withdrawal_id),
        )
        await db.commit()
        return cur.rowcount > 0

    @staticmethod
    async def get_stats() -> dict:
        db = await get_db()

        async with db.execute("SELECT COUNT(*) as cnt FROM users") as cur:
            total_users = (await cur.fetchone())["cnt"]

        async with db.execute(
            "SELECT COUNT(*) as cnt FROM listings WHERE is_active = 1"
        ) as cur:
            active_listings = (await cur.fetchone())["cnt"]

        async with db.execute(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as vol
               FROM orders WHERE status IN ('confirmed', 'delivered', 'paid_out')"""
        ) as cur:
            row = await cur.fetchone()
            total_orders = row["cnt"]
            total_volume_micro = row["vol"]

        async with db.execute(
            "SELECT COALESCE(SUM(amount), 0) as fees FROM transactions WHERE type = 'fee'"
        ) as cur:
            platform_fees_micro = (await cur.fetchone())["fees"]

        async with db.execute(
            "SELECT COUNT(*) as cnt FROM disputes WHERE status = 'open'"
        ) as cur:
            open_disputes = (await cur.fetchone())["cnt"]

        async with db.execute(
            "SELECT COUNT(*) as cnt FROM withdrawals WHERE status = 'pending'"
        ) as cur:
            pending_withdrawals = (await cur.fetchone())["cnt"]

        return {
            "total_users": total_users,
            "active_listings": active_listings,
            "total_orders": total_orders,
            "total_volume_micro": int(total_volume_micro),
            "platform_fees_micro": int(platform_fees_micro),
            "open_disputes": open_disputes,
            "pending_withdrawals": pending_withdrawals,
        }

    @staticmethod
    async def ban_user(ghost_id: str) -> Optional[int]:
        """Возвращает tg_id забаненного юзера или None."""
        db = await get_db()
        async with db.execute(
            "SELECT tg_id FROM users WHERE ghost_id = ?", (ghost_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        await db.execute(
            "UPDATE users SET is_banned = 1 WHERE ghost_id = ?", (ghost_id,)
        )
        await db.commit()
        return row["tg_id"]

    @staticmethod
    async def unban_user(ghost_id: str) -> bool:
        db = await get_db()
        cur = await db.execute(
            "UPDATE users SET is_banned = 0 WHERE ghost_id = ?", (ghost_id,)
        )
        await db.commit()
        return cur.rowcount > 0


class _NoOpRollback(Exception):
    pass
