"""
stats_service.py — аналитика для дашборда.
"""
from typing import List
from database.db import get_db, fmt


class StatsService:

    @staticmethod
    async def daily_volume(days: int = 30) -> List[dict]:
        """Оборот по дням за последние N дней."""
        db = await get_db()
        async with db.execute(
            """SELECT
                 date(created_at) as day,
                 COUNT(*) as orders,
                 COALESCE(SUM(amount), 0) as volume,
                 COALESCE(SUM(fee), 0) as fees
               FROM orders
               WHERE status IN ('confirmed', 'paid_out')
               AND created_at >= datetime('now', ? || ' days')
               GROUP BY day
               ORDER BY day ASC""",
            (f"-{days}",),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def top_categories(limit: int = 10) -> List[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT
                 c.name, c.emoji,
                 COUNT(l.id) as listing_count,
                 COUNT(o.id) as order_count,
                 COALESCE(SUM(o.amount), 0) as volume
               FROM categories c
               LEFT JOIN listings l ON l.category_id = c.id AND l.is_active = 1
               LEFT JOIN orders o ON o.listing_id = l.id
                   AND o.status IN ('confirmed', 'paid_out')
               WHERE c.parent_id IS NOT NULL
               GROUP BY c.id
               ORDER BY volume DESC LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def top_sellers(limit: int = 10) -> List[dict]:
        db = await get_db()
        async with db.execute(
            """SELECT
                 u.ghost_id,
                 COUNT(o.id) as deals,
                 COALESCE(SUM(o.amount), 0) as volume,
                 COALESCE(AVG(r.rating), 0) as avg_rating
               FROM users u
               JOIN orders o ON o.seller_id = u.id
                   AND o.status IN ('confirmed', 'paid_out')
               LEFT JOIN reviews r ON r.target_id = u.id
               GROUP BY u.id
               ORDER BY volume DESC LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    async def full_summary() -> dict:
        db = await get_db()

        async with db.execute("SELECT COUNT(*) as c FROM users") as cur:
            users = (await cur.fetchone())["c"]

        async with db.execute(
            "SELECT COUNT(*) as c FROM listings WHERE is_active = 1"
        ) as cur:
            active_listings = (await cur.fetchone())["c"]

        async with db.execute(
            """SELECT COUNT(*) as c, COALESCE(SUM(amount),0) as v, COALESCE(SUM(fee),0) as f
               FROM orders WHERE status IN ('confirmed','paid_out')"""
        ) as cur:
            row = await cur.fetchone()
            total_orders = row["c"]
            total_volume = row["v"]
            total_fees = row["f"]

        async with db.execute(
            """SELECT COUNT(*) as c, COALESCE(SUM(amount),0) as v, COALESCE(SUM(fee),0) as f
               FROM orders WHERE status IN ('confirmed','paid_out')
               AND created_at >= datetime('now', '-30 days')"""
        ) as cur:
            row = await cur.fetchone()
            month_orders = row["c"]
            month_volume = row["v"]
            month_fees = row["f"]

        async with db.execute(
            "SELECT COUNT(*) as c FROM disputes WHERE status = 'open'"
        ) as cur:
            open_disputes = (await cur.fetchone())["c"]

        async with db.execute(
            "SELECT COUNT(*) as c FROM withdrawals WHERE status = 'pending'"
        ) as cur:
            pending_withdrawals = (await cur.fetchone())["c"]

        async with db.execute(
            "SELECT COUNT(*) as c FROM listing_boosts WHERE expires_at > datetime('now')"
        ) as cur:
            active_boosts = (await cur.fetchone())["c"]

        return {
            "users": users,
            "active_listings": active_listings,
            "total_orders": total_orders,
            "total_volume": total_volume,
            "total_fees": total_fees,
            "month_orders": month_orders,
            "month_volume": month_volume,
            "month_fees": month_fees,
            "open_disputes": open_disputes,
            "pending_withdrawals": pending_withdrawals,
            "active_boosts": active_boosts,
        }

    @staticmethod
    async def generate_report_text(lang: str = "en") -> str:
        """Генерирует текстовый отчёт для Telegraph/Telegram."""
        s = await StatsService.full_summary()
        cats = await StatsService.top_categories(5)
        sellers = await StatsService.top_sellers(5)

        if lang == "ru":
            lines = [
                "📊 <b>Anonex — Отчёт</b>\n",
                f"👤 Пользователей: <b>{s['users']}</b>",
                f"📋 Активных объявлений: <b>{s['active_listings']}</b>",
                f"🚀 Активных бустов: <b>{s['active_boosts']}</b>",
                "",
                "📦 <b>Всего</b>",
                f"  Сделок: {s['total_orders']}",
                f"  Оборот: {fmt(s['total_volume'])} USDT",
                f"  Комиссии: {fmt(s['total_fees'])} USDT",
                "",
                "📅 <b>За 30 дней</b>",
                f"  Сделок: {s['month_orders']}",
                f"  Оборот: {fmt(s['month_volume'])} USDT",
                f"  Комиссии: {fmt(s['month_fees'])} USDT",
                "",
                f"⚠️ Открытых споров: {s['open_disputes']}",
                f"📤 Ожидают вывода: {s['pending_withdrawals']}",
                "",
                "🏆 <b>Топ категорий</b>",
            ]
            for c in cats:
                lines.append(
                    f"  {c['emoji']} {c['name']}: {c['order_count']} сделок, "
                    f"{fmt(c['volume'])} USDT"
                )
            lines += ["", "🥇 <b>Топ продавцов</b>"]
            for s2 in sellers:
                lines.append(
                    f"  <code>{s2['ghost_id']}</code>: {s2['deals']} сделок, "
                    f"{fmt(s2['volume'])} USDT, ⭐{s2['avg_rating']:.1f}"
                )
        else:
            lines = [
                "📊 <b>Anonex — Report</b>\n",
                f"👤 Users: <b>{s['users']}</b>",
                f"📋 Active listings: <b>{s['active_listings']}</b>",
                f"🚀 Active boosts: <b>{s['active_boosts']}</b>",
                "",
                "📦 <b>All time</b>",
                f"  Deals: {s['total_orders']}",
                f"  Volume: {fmt(s['total_volume'])} USDT",
                f"  Fees: {fmt(s['total_fees'])} USDT",
                "",
                "📅 <b>Last 30 days</b>",
                f"  Deals: {s['month_orders']}",
                f"  Volume: {fmt(s['month_volume'])} USDT",
                f"  Fees: {fmt(s['month_fees'])} USDT",
                "",
                f"⚠️ Open disputes: {s['open_disputes']}",
                f"📤 Pending withdrawals: {s['pending_withdrawals']}",
                "",
                "🏆 <b>Top categories</b>",
            ]
            for c in cats:
                lines.append(
                    f"  {c['emoji']} {c['name']}: {c['order_count']} deals, "
                    f"{fmt(c['volume'])} USDT"
                )
            lines += ["", "🥇 <b>Top sellers</b>"]
            for s2 in sellers:
                lines.append(
                    f"  <code>{s2['ghost_id']}</code>: {s2['deals']} deals, "
                    f"{fmt(s2['volume'])} USDT, ⭐{s2['avg_rating']:.1f}"
                )

        return "\n".join(lines)
