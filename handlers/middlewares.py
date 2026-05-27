import asyncio
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from services.user_service import UserService


class UserMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, (Message, CallbackQuery)):
            tg_user = event.from_user

        if tg_user:
            user = await UserService.get_by_tg_id(tg_user.id)
            if user is None:
                user = await UserService.get_or_create(tg_user.id)
            data["user"] = user

            if user.get("is_banned"):
                if isinstance(event, Message):
                    await event.answer("🚫 Аккаунт заблокирован.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Заблокирован.", show_alert=True)
                return
        else:
            data["user"] = None

        return await handler(event, data)


class ThrottleMiddleware(BaseMiddleware):
    """
    Rate-limiter в памяти с периодической чисткой старых записей.
    """

    def __init__(self, rate: int = 5, period: float = 3.0):
        self._rate = rate
        self._period = period
        self._history: dict = {}  # {tg_id: [timestamps]}
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = 60.0  # чистим раз в минуту

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, (Message, CallbackQuery)):
            tg_user = event.from_user

        if tg_user:
            now = time.monotonic()

            # Периодическая чистка — удаляем юзеров с протухшими записями
            if now - self._last_cleanup > self._cleanup_interval:
                self._last_cleanup = now
                stale = [
                    uid for uid, ts_list in self._history.items()
                    if not ts_list or (now - ts_list[-1]) > self._period
                ]
                for uid in stale:
                    del self._history[uid]

            ts_list = self._history.get(tg_user.id, [])
            # Фильтруем устаревшие
            ts_list = [t for t in ts_list if now - t < self._period]

            if len(ts_list) >= self._rate:
                if isinstance(event, CallbackQuery):
                    await event.answer("⏱ Подожди.", show_alert=True)
                self._history[tg_user.id] = ts_list
                return

            ts_list.append(now)
            self._history[tg_user.id] = ts_list

        return await handler(event, data)
