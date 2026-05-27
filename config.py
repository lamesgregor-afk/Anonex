"""
config.py

Фиксы:
- PLATFORM_FEE_PERCENT и REFERRAL_SHARE_PERCENT теперь int (целые проценты)
  → расчёт fee остаётся целочисленным, пишется в INTEGER колонки без float
- Pydantic v2 совместимость: model_config вместо класса Config, без cached_property
  (заменено на ручной мемо через _admin_ids_cache)
- BOT_USERNAME удалён из Settings (BaseSettings нельзя безопасно мутировать после init)
  → перенесён в app_state.py
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    BOT_TOKEN: str
    CRYPTOBOT_TOKEN: str
    ADMIN_IDS: str = ""
    WEBHOOK_URL: str = ""
    PORT: int = 8080

    REDIS_URL: str = ""

    # Бизнес-логика — целые проценты, чтобы расчёт оставался в int
    PLATFORM_FEE_PERCENT: int = 10
    REFERRAL_SHARE_PERCENT: int = 50
    ESCROW_AUTO_CONFIRM_HOURS: int = 48
    WITHDRAWAL_HOLD_DAYS: int = 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Ручной кэш через приватное поле — Pydantic v2-совместимо
    _admin_ids_cache: Optional[List[int]] = None

    @property
    def admin_ids(self) -> List[int]:
        if self._admin_ids_cache is None:
            if not self.ADMIN_IDS:
                object.__setattr__(self, "_admin_ids_cache", [])
            else:
                ids = [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]
                object.__setattr__(self, "_admin_ids_cache", ids)
        return self._admin_ids_cache  # type: ignore

    def get_admin_ids(self) -> List[int]:
        return self.admin_ids


settings = Settings()
