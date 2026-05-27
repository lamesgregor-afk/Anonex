"""
crypto_service.py

Интеграция с CryptoBot (pay.crypt.bot).
Документация: https://help.crypt.bot/crypto-pay-api

Изменения vs оригинала:
- Один ClientSession на весь lifetime приложения (пул соединений)
- HMAC-SHA256 верификация вебхука (не сравнение токенов)
- spend_id использует withdrawal_id — уникальный идемпотентный ключ
- print() заменён на logging
- amount принимается в микро-USDT, конвертируется в строку USDT перед отправкой
"""
import aiohttp
import asyncio
import hashlib
import hmac
import json
import logging
from typing import Optional
from decimal import Decimal
from config import settings

logger = logging.getLogger(__name__)

CRYPTOBOT_API = "https://pay.crypt.bot/api"

# Один сессионный объект на весь процесс
_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        async with _session_lock:
            if _session is None or _session.closed:
                connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
                _session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=aiohttp.ClientTimeout(total=15),
                )
    return _session


async def close_session():
    """Вызвать при завершении приложения."""
    global _session
    if _session and not _session.closed:
        await _session.close()


def _micro_to_str(micro: int) -> str:
    """Конвертирует микро-USDT в строку с 6 знаками '5.500000' для API."""
    val = (Decimal(micro) / Decimal(1_000_000)).quantize(Decimal("0.000001"))
    return str(val)


class CryptoService:

    @staticmethod
    def _headers() -> dict:
        return {"Crypto-Pay-API-Token": settings.CRYPTOBOT_TOKEN}

    @classmethod
    async def create_invoice(
        cls,
        amount_micro: int,
        order_id: int,
        description: str = "",
        bot_username: str = "",
    ) -> Optional[dict]:
        """
        Создаёт инвойс в USDT.
        Возвращает {invoice_id, pay_url, status} или None при ошибке.
        """
        amount_str = _micro_to_str(amount_micro)
        # paid_btn_url требует валидный URL с username, не bot_id
        paid_btn_url = (
            f"https://t.me/{bot_username}"
            if bot_username
            else "https://t.me/CryptoBot"
        )
        payload = {
            "asset": "USDT",
            "amount": amount_str,
            "description": description or f"GhostMarket order #{order_id}",
            "payload": str(order_id),
            "paid_btn_name": "callback",
            "paid_btn_url": paid_btn_url,
            "allow_comments": False,
            "allow_anonymous": True,
        }
        try:
            session = await _get_session()
            async with session.post(
                f"{CRYPTOBOT_API}/createInvoice",
                json=payload,
                headers=cls._headers(),
            ) as resp:
                data = await resp.json()
            if data.get("ok"):
                result = data["result"]
                return {
                    "invoice_id": str(result["invoice_id"]),
                    "pay_url": result["pay_url"],
                    "status": result["status"],
                }
            logger.warning("[CryptoService] createInvoice error: %s", data)
        except Exception:
            logger.exception("[CryptoService] create_invoice failed")
        return None

    @classmethod
    async def get_invoice(cls, invoice_id: str) -> Optional[dict]:
        try:
            session = await _get_session()
            async with session.get(
                f"{CRYPTOBOT_API}/getInvoices",
                params={"invoice_ids": invoice_id},
                headers=cls._headers(),
            ) as resp:
                data = await resp.json()
            if data.get("ok") and data["result"]["items"]:
                return data["result"]["items"][0]
            logger.warning("[CryptoService] getInvoices empty: %s", data)
        except Exception:
            logger.exception("[CryptoService] get_invoice failed")
        return None

    @classmethod
    async def transfer(
        cls,
        tg_user_id: int,
        amount_micro: int,
        withdrawal_id: int,
        comment: str = "",
    ) -> bool:
        """
        Переводит USDT пользователю через CryptoBot Transfer.
        spend_id = gm_w{withdrawal_id} — гарантирует идемпотентность.
        """
        payload = {
            "user_id": tg_user_id,
            "asset": "USDT",
            "amount": _micro_to_str(amount_micro),
            "comment": comment or "GhostMarket payout",
            "spend_id": f"gm_w{withdrawal_id}",
        }
        try:
            session = await _get_session()
            async with session.post(
                f"{CRYPTOBOT_API}/transfer",
                json=payload,
                headers=cls._headers(),
            ) as resp:
                data = await resp.json()
            if data.get("ok"):
                return True
            logger.warning("[CryptoService] transfer error: %s", data)
        except Exception:
            logger.exception("[CryptoService] transfer failed")
        return False

    @classmethod
    def verify_webhook(cls, body: bytes, signature: str) -> bool:
        """
        HMAC-SHA256 верификация вебхука CryptoBot.
        Ключ = SHA256(api_token), подпись = HMAC(key, body).
        Без этой проверки злоумышленник может подделать событие оплаты.
        """
        try:
            key = hashlib.sha256(settings.CRYPTOBOT_TOKEN.encode()).digest()
            expected = hmac.new(key, body, hashlib.sha256).hexdigest()
            # constant-time compare — защита от timing attack
            return hmac.compare_digest(expected, signature.lower())
        except Exception:
            logger.exception("[CryptoService] verify_webhook failed")
            return False
