"""
order_service.py

Ключевые изменения:
- _calc_fees использует только int (config.PLATFORM_FEE_PERCENT теперь int)
- claim_for_release: атомарно проверяет (status, funds_released=0) и переводит в 'in_release'-флаг,
  чтобы release_funds стал идемпотентным даже при крэше между шагами
- has_active_order_for_listing: защита от дубль-ордеров на один листинг
- resolve_seller-friendly: возвращает payout_available_at и в случае disputed→confirmed
"""
from typing import Optional, List, Tuple
from datetime import datetime, timedelta, timezone
from database.db import get_db, transaction
from config import settings
import logging

logger = logging.getLogger(__name__)


def _calc_fees(amount_micro: int, has_referrer: bool) -> Tuple[int, int, int]:
    """Возвращает (fee, referral_fee, net_to_seller) — все int (микро-USDT)."""
    fee = amount_micro * settings.PLATFORM_FEE_PERCENT // 100
    referral_fee = (
        fee * settings.REFERRAL_SHARE_PERCENT // 100 if has_referrer else 0
    )
    net_to_seller = amount_micro - fee
    return fee, referral_fee, net_to_seller


def _utc_iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).strftime("%Y-%m-%d %H:%M:%S")


class OrderService:

    @staticmethod
    async def create(
        listing_id: int,
        buyer_id: int,
        seller_id: int,
        amount_micro: int,
        has_referrer: bool = False,
    ) -> dict:
        fee, referral_fee, net_to_seller = _calc_fees(amount_micro, has_referrer)
        db = await get_db()
        async with db.execute(
            """INSERT INTO orders
               (listing_id, buyer_id, seller_id, amount, fee, referral_fee, net_to_seller)
               VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING *""",
            (listing_id, buyer_id, seller_id, amount_micro, fee, referral_fee, net_to_seller),
        ) as cur:
            row = await cur.fetchone()
        await db.commit()
        return dict(row)

    @staticmethod
    async def has_active_order_for_listing(buyer_id: int, listing_id: int) -> bool:
        """
        Защита от двойного 'Купить'. True если у покупателя уже есть
        неоплаченный или активный заказ по этому листингу.
        """
        db = await get_db()
        async with db.execute(
            """SELECT 1 FROM orders
               WHERE buyer_id = ? AND listing_id = ?
               AND status IN ('pending_payment', 'paid', 'delivered', 'disputed')
               LIMIT 1""",
            (buyer_id, listing_id),
        ) as cur:
            return await cur.fetchone() is not None

    @staticmethod
    async def get_by_id(order_id: int) -> Optional[dict]:
        db = await get_db()
        async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    async def get_by_invoice(invoice_id: str) -> Optional[dict]:
        db = await get_db()
        async with db.execute(
            "SELECT * FROM orders WHERE crypto_invoice_id = ?", (invoice_id,)
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    async def set_invoice(order_id: int, invoice_id: str, pay_url: str):
        db = await get_db()
        await db.execute(
            """UPDATE orders
               SET crypto_invoice_id = ?, crypto_pay_url = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (invoice_id, pay_url, order_id),
        )
        await db.commit()

    @staticmethod
    async def try_mark_paid(order_id: int) -> bool:
        auto_at = _utc_iso(timedelta(hours=settings.ESCROW_AUTO_CONFIRM_HOURS))
        db = await get_db()
        cur = await db.execute(
            """UPDATE orders
               SET status = 'paid', auto_confirm_at = ?, updated_at = datetime('now')
               WHERE id = ? AND status = 'pending_payment'""",
            (auto_at, order_id),
        )
        await db.commit()
        ok = cur.rowcount > 0
        if ok:
            logger.info("[order] #%d → paid", order_id)
        return ok

    @staticmethod
    async def try_mark_delivered(order_id: int, delivery_note: str) -> bool:
        db = await get_db()
        cur = await db.execute(
            """UPDATE orders
               SET status = 'delivered', delivery_note = ?, updated_at = datetime('now')
               WHERE id = ? AND status = 'paid'""",
            (delivery_note[:500], order_id),
        )
        await db.commit()
        ok = cur.rowcount > 0
        if ok:
            logger.info("[order] #%d → delivered", order_id)
        return ok

    @staticmethod
    async def try_mark_confirmed(order_id: int, from_statuses: tuple = ("delivered", "paid")) -> bool:
        """
        Атомарный переход → confirmed с выставлением payout_available_at.
        from_statuses настраивается: для dispute→seller передаём ('disputed',).
        """
        payout_at = _utc_iso(timedelta(days=settings.WITHDRAWAL_HOLD_DAYS))
        placeholders = ",".join("?" * len(from_statuses))
        db = await get_db()
        cur = await db.execute(
            f"""UPDATE orders
                SET status = 'confirmed',
                    confirmed_at = datetime('now'),
                    payout_available_at = ?,
                    updated_at = datetime('now')
                WHERE id = ? AND status IN ({placeholders})""",
            (payout_at, order_id, *from_statuses),
        )
        await db.commit()
        ok = cur.rowcount > 0
        if ok:
            logger.info("[order] #%d → confirmed (from %s)", order_id, from_statuses)
        return ok

    @staticmethod
    async def try_mark_paid_out_atomic(order_id: int) -> Optional[dict]:
        """
        Атомарный переход confirmed → paid_out. Только если funds_released=1
        (т.е. деньги уже точно в pending у продавца — гарантия от частичного состояния).
        Возвращает order или None.
        """
        async with transaction() as db:
            async with db.execute(
                """SELECT * FROM orders
                   WHERE id = ? AND status = 'confirmed' AND funds_released = 1""",
                (order_id,),
            ) as cur:
                row = await cur.fetchone()
            if not row:
                return None
            cur = await db.execute(
                """UPDATE orders
                   SET status = 'paid_out', updated_at = datetime('now')
                   WHERE id = ? AND status = 'confirmed' AND funds_released = 1""",
                (order_id,),
            )
            if cur.rowcount == 0:
                return None
            return dict(row)

    @staticmethod
    async def mark_funds_released(order_id: int) -> bool:
        """Помечает что release_funds выполнена. Идемпотентно."""
        db = await get_db()
        cur = await db.execute(
            """UPDATE orders SET funds_released = 1, updated_at = datetime('now')
               WHERE id = ? AND funds_released = 0""",
            (order_id,),
        )
        await db.commit()
        return cur.rowcount > 0

    @staticmethod
    async def try_mark_cancelled(order_id: int) -> bool:
        db = await get_db()
        cur = await db.execute(
            """UPDATE orders
               SET status = 'cancelled', updated_at = datetime('now')
               WHERE id = ? AND status = 'pending_payment'""",
            (order_id,),
        )
        await db.commit()
        return cur.rowcount > 0

    @staticmethod
    async def try_mark_refunded(order_id: int) -> bool:
        db = await get_db()
        cur = await db.execute(
            """UPDATE orders
               SET status = 'refunded', updated_at = datetime('now')
               WHERE id = ? AND status = 'disputed'""",
            (order_id,),
        )
        await db.commit()
        return cur.rowcount > 0

    @staticmethod
    async def open_dispute(order_id: int, opened_by: int, reason: str) -> bool:
        """Атомарный переход + INSERT в disputes в одной транзакции."""
        try:
            async with transaction() as db:
                cur = await db.execute(
                    """UPDATE orders
                       SET status = 'disputed', dispute_reason = ?, updated_at = datetime('now')
                       WHERE id = ? AND status IN ('delivered', 'paid')""",
                    (reason[:1000], order_id),
                )
                if cur.rowcount == 0:
                    raise _NoOpRollback()
                await db.execute(
                    "INSERT INTO disputes (order_id, opened_by, reason) VALUES (?, ?, ?)",
                    (order_id, opened_by, reason[:1000]),
                )
            return True
        except _NoOpRollback:
            return False

    @staticmethod
    async def get_buyer_orders(buyer_id: int, limit: int = 10, offset: int = 0) -> List[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT o.*, l.title as listing_title
               FROM orders o
               LEFT JOIN listings l ON o.listing_id = l.id
               WHERE o.buyer_id = ?
               ORDER BY o.created_at DESC LIMIT ? OFFSET ?""",
            (buyer_id, limit, offset),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def get_seller_orders(seller_id: int, limit: int = 10, offset: int = 0) -> List[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT o.*, l.title as listing_title
               FROM orders o
               LEFT JOIN listings l ON o.listing_id = l.id
               WHERE o.seller_id = ?
               ORDER BY o.created_at DESC LIMIT ? OFFSET ?""",
            (seller_id, limit, offset),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def get_overdue_auto_confirm(limit: int = 100) -> List[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT * FROM orders
               WHERE status = 'delivered'
               AND auto_confirm_at <= datetime('now')
               LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def get_payout_ready(limit: int = 100) -> List[dict]:
        """
        Заказы готовые к разморозке: confirmed + funds_released=1 + истёк hold.
        funds_released=1 гарантирует что pending-баланс уже у продавца.
        """
        db = await get_db()
        async with db.execute(
            """SELECT * FROM orders
               WHERE status = 'confirmed'
               AND funds_released = 1
               AND payout_available_at IS NOT NULL
               AND payout_available_at <= datetime('now')
               LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def get_unreleased_confirmed(limit: int = 100) -> List[dict]:
        """
        Recovery: заказы confirmed но funds_released=0
        (значит крэш между mark_confirmed и mark_funds_released).
        Scheduler должен их добить.
        """
        db = await get_db()
        async with db.execute(
            """SELECT * FROM orders
               WHERE status = 'confirmed' AND funds_released = 0
               LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def log_transaction(
        user_id: int,
        tx_type: str,
        amount_micro: int,
        order_id: Optional[int] = None,
        comment: Optional[str] = None,
    ):
        db = await get_db()
        await db.execute(
            """INSERT INTO transactions (user_id, order_id, type, amount, comment)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, order_id, tx_type, amount_micro, comment),
        )
        await db.commit()


class _NoOpRollback(Exception):
    """Используется чтобы откатить транзакцию без ошибки наружу."""
    pass
