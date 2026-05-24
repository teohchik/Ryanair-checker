# Ryanair Price Tracker Bot

A Telegram bot that monitors Ryanair flight prices for saved routes and sends you a notification whenever a new lowest price appears.

## Features

- Search airports by city name, airport name, or IATA code
- Track one-way flights with a specific date or a date range
- Date picker shows only days with available fares (live API check)
- Automatic price checks every 6 hours
- Alerts only when a new minimum price is found
- Admin notifications for new users and new trackers

## Quick start

```bash
# 1. Create and activate virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — set BOT_TOKEN and ADMIN_ID

# 4. Create the database
alembic upgrade head

# 5. Run
python -m app
```

## Docker

```bash
cp .env.example .env
# Edit .env

docker compose up --build -d
docker compose logs -f bot
```

## Bot commands

| Command | Description |
|---------|-------------|
| `/start` | Main menu |
| `/add` | Add a new price tracker |
| `/my` | View and manage your trackers |
| `/help` | Usage guide |

## Admin commands

| Command | Description |
|---------|-------------|
| `/stats` | Total users, active trackers, last check time |

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BOT_TOKEN` | Bot token from @BotFather | — |
| `ADMIN_ID` | Telegram user ID of the admin | — |
| `DATABASE_URL` | SQLAlchemy async DB URL | `sqlite+aiosqlite:///./data/bot.db` |
| `CHECK_INTERVAL_HOURS` | How often to check prices | `6` |
| `CURRENCY` | Fare currency | `EUR` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_JSON` | JSON log format (recommended for Docker) | `false` |
