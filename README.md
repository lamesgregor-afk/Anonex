# 👻 GhostMarket Bot

Анонимный P2P-маркетплейс в Telegram. Файлы, услуги, консультации за USDT через CryptoBot.

---

## Структура проекта

```
ghostmarket/
├── main.py                  # Точка входа
├── config.py                # Настройки через .env
├── scheduler.py             # Фоновые задачи (APScheduler)
├── requirements.txt
├── .env.example
├── database/
│   ├── __init__.py
│   └── db.py               # Схема SQLite + подключение
├── services/
│   ├── __init__.py
│   ├── user_service.py     # Пользователи, балансы, рефералы
│   ├── listing_service.py  # Объявления
│   ├── order_service.py    # Заказы, эскроу, транзакции
│   ├── crypto_service.py   # CryptoBot API
│   └── admin_service.py    # Споры, выводы, статистика
└── handlers/
    ├── __init__.py
    ├── middlewares.py       # UserMiddleware
    ├── keyboards.py        # Все клавиатуры
    ├── start.py            # /start, /help, реферальная
    ├── listings.py         # Маркет, создание объявлений
    ├── orders.py           # Покупка, эскроу, доставка, споры
    ├── wallet.py           # Кошелёк, вывод, история
    └── admin.py            # Панель администратора
```

---

## Как запустить локально

### 1. Клонируй и создай окружение

```bash
git clone <repo>
cd ghostmarket
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Создай .env файл

```bash
cp .env.example .env
```

Заполни `.env`:

```env
BOT_TOKEN=1234567890:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CRYPTOBOT_TOKEN=1234567:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_IDS=123456789
# WEBHOOK_URL оставь пустым для polling (локально)
```

Где взять токены:
- **BOT_TOKEN** — создай бота через [@BotFather](https://t.me/BotFather)
- **CRYPTOBOT_TOKEN** — зарегистрируйся на [pay.crypt.bot](https://t.me/CryptoBot), создай приложение
- **ADMIN_IDS** — твой Telegram ID (узнай через [@userinfobot](https://t.me/userinfobot))

### 3. Запусти

```bash
python main.py
```

База данных `ghostmarket.db` создастся автоматически.

---

## Деплой на Railway

### 1. Создай аккаунт
Зарегистрируйся на [railway.app](https://railway.app) (есть бесплатный план).

### 2. Создай новый проект
- New Project → Deploy from GitHub repo
- Выбери репозиторий с ботом

### 3. Задай переменные окружения
В Railway → Variables добавь:

| Variable | Value |
|----------|-------|
| `BOT_TOKEN` | токен бота |
| `CRYPTOBOT_TOKEN` | токен CryptoBot |
| `ADMIN_IDS` | твой Telegram ID |
| `WEBHOOK_URL` | `https://your-app.up.railway.app` (после деплоя) |
| `PORT` | `8080` |

### 4. Задеплой
Railway автоматически запустит `python main.py`.  
После деплоя скопируй URL вида `https://xxx.up.railway.app` и вставь в `WEBHOOK_URL`.

### 5. Перезапусти сервис
Settings → Restart — вебхук установится автоматически.

---

## Бизнес-логика

### Флоу сделки

```
Покупатель находит товар
         ↓
    Нажимает "Купить"
         ↓
   Создаётся инвойс CryptoBot
         ↓
   Покупатель платит USDT
         ↓
   Деньги в ЭСКРОУ (заморожены)
         ↓
   Продавец передаёт товар
         ↓
   Покупатель подтверждает (или 48ч → авто)
         ↓
   Деньги → продавцу в PENDING (7 дней hold)
         ↓
   Через 7 дней → доступны для вывода
```

### Комиссии

- Платформа берёт **10%** от суммы сделки
- Если у покупателя есть реферер — он получает **50% от этой комиссии** (5% от суммы)
- Реферальные выплаты **без задержки** (сразу на баланс)
- Продавцу уходит **90%** от суммы (или 85% если покупатель пришёл по рефералу)

### Споры

Покупатель может открыть спор по доставленному заказу.  
Деньги остаются заморожены. Администратор решает через `/admin` → Споры:
- **Вернуть покупателю** → полный возврат
- **Продавцу** → деньги идут продавцу (с hold 7 дней)

---

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Регистрация (ghost ID) |
| `/help` | Как это работает |
| `/admin` | Админ-панель (только для ADMIN_IDS) |
| `/ban ghost_xxxxx` | Забанить пользователя |
| `/unban ghost_xxxxx` | Разбанить пользователя |

---

## Настройка CryptoBot Webhook (опционально)

CryptoBot может присылать webhook при оплате. Для этого:

1. Открой [@CryptoBot](https://t.me/CryptoBot) → My Apps → выбери приложение
2. Webhook URL: `https://your-app.up.railway.app/cryptobot-webhook`
3. В `main.py` добавь обработчик этого пути (в текущей версии используется polling через кнопку "Проверить оплату")

---

## Важные замечания

- **SQLite** подходит для старта, при высокой нагрузке замени на PostgreSQL
- **MemoryStorage** для FSM — при рестарте состояния сбросятся. Для прода используй RedisStorage
- Переводы через CryptoBot Transfer требуют, чтобы получатель запустил [@CryptoBot](https://t.me/CryptoBot)
- Для вывода на внешние адреса (TRC20) нужна интеграция с биржей или ручная обработка
