# Ryanair Price Tracker Bot

Telegram-бот для відстеження цін на рейси Ryanair. Перевіряє ціни кожні 6 годин і надсилає сповіщення, коли з'являється нова найнижча ціна.

## Функції

- Відстеження one-way рейсів між будь-якими аеропортами Ryanair
- Режими дат: конкретний день або діапазон
- Автоматична перевірка цін кожні 6 годин
- Сповіщення при новому мінімумі ціни
- Адмін отримує сповіщення про нових користувачів і нові трекери

## Швидкий старт (локально)

```bash
# 1. Встановити залежності
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Налаштувати середовище
cp .env.example .env
# Відредагуй .env — вкажи BOT_TOKEN і ADMIN_ID

# 3. Створити БД
alembic upgrade head

# 4. Запустити
python -m app
```

## Docker

```bash
cp .env.example .env
# Відредагуй .env

docker compose up --build -d
docker compose logs -f bot
```

## Команди бота

| Команда | Опис |
|---------|------|
| `/start` | Головне меню |
| `/add` | Додати новий трекер |
| `/my` | Переглянути та видалити трекери |
| `/help` | Довідка |

## Адмін-команди

| Команда | Опис |
|---------|------|
| `/stats` | Статистика (юзери, трекери, останній запуск) |

## Структура проєкту

```
app/
├── config.py            # Налаштування (pydantic-settings)
├── db/                  # SQLAlchemy моделі та сесія
├── ryanair/             # HTTP-клієнт та схеми Ryanair API
├── services/            # Бізнес-логіка
│   ├── subscriptions.py # CRUD підписок
│   ├── price_tracker.py # Перевірка цін
│   └── notifier.py      # Відправка повідомлень
├── middlewares/         # DB-сесія, реєстрація юзерів
├── handlers/            # Telegram-хендлери
├── keyboards/           # Клавіатури
├── filters/             # Фільтри (IsAdmin)
└── scheduler.py         # APScheduler

```

## Налаштування `.env`

| Змінна | Опис | За замовчуванням |
|--------|------|-----------------|
| `BOT_TOKEN` | Токен бота від @BotFather | — |
| `ADMIN_ID` | Telegram ID адміна | — |
| `DATABASE_URL` | URL бази даних | `sqlite+aiosqlite:///./data/bot.db` |
| `CHECK_INTERVAL_HOURS` | Інтервал перевірки в годинах | `6` |
| `CURRENCY` | Валюта | `EUR` |
| `LOG_LEVEL` | Рівень логування | `INFO` |
| `LOG_JSON` | JSON-формат логів (для Docker) | `false` |
