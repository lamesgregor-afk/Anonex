"""
app_state.py

Глобальное runtime-состояние, которое заполняется при старте.
Не путать с config.Settings (только статические значения из .env).
"""


class AppState:
    bot_username: str = ""

    @classmethod
    def set_bot_username(cls, username: str):
        cls.bot_username = username


app_state = AppState()
