"""
i18n — простой переводчик.

Язык хранится в таблице users.lang (TEXT, default 'en').
get(user, key, **kwargs) → форматированная строка.
"""
from typing import Optional
from .en import T as EN
from .ru import T as RU

_LANGS = {"en": EN, "ru": RU}
DEFAULT_LANG = "en"


def get(user: Optional[dict], key: str, **kwargs) -> str:
    lang = (user or {}).get("lang", DEFAULT_LANG)
    strings = _LANGS.get(lang, EN)
    template = strings.get(key) or EN.get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    return template


def tx_type_label(user: Optional[dict], tx_type: str) -> str:
    lang = (user or {}).get("lang", DEFAULT_LANG)
    strings = _LANGS.get(lang, EN)
    return strings.get("tx_types", {}).get(tx_type, tx_type)
