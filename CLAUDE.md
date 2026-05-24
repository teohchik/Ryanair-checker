# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup (first time)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in BOT_TOKEN and ADMIN_ID

# Database
alembic upgrade head                          # apply all migrations
alembic revision --autogenerate -m "name"     # generate new migration after model changes

# Run
python -m app

# Docker
docker compose up --build -d
docker compose logs -f bot
```

## Architecture

The bot is structured in strict layers — handlers never contain business logic:

```
app/
├── __main__.py          # bootstrap: bot, dispatcher, middleware registration, scheduler start
├── config.py            # Settings (pydantic-settings, reads .env); imported as singleton `settings`
├── db/
│   ├── models.py        # User, Subscription (DateMode enum), PriceSnapshot
│   └── session.py       # engine + AsyncSessionFactory
├── ryanair/
│   ├── client.py        # RyanairClient — httpx + tenacity retry; get_cheapest_per_day(), get_routes_from()
│   ├── schemas.py       # Pydantic models for API responses (MonthlyFares, Fare, FarePrice)
│   └── airports.py      # Airport dataclass, in-memory cache loaded at startup; search(), get_airport()
├── services/
│   ├── subscriptions.py # CRUD: create, list, soft-delete, get_all_active
│   ├── price_tracker.py # check_subscription() + run_check() (the 6h job); stores PriceSnapshot
│   └── notifier.py      # Notifier wraps Bot.send_message with RetryAfter/Forbidden handling
├── middlewares/
│   ├── db.py            # DbSessionMiddleware — creates AsyncSession per update, injects as data["session"]
│   └── user_registration.py  # upsert User on every update; fires admin "New user" notification
├── filters/admin.py     # IsAdmin filter (checks against settings.admin_id)
├── keyboards/inline.py  # all InlineKeyboardMarkup builders + format_subscriptions_text()
├── handlers/
│   ├── add_subscription.py   # FSM AddSub: origin→destination→date_mode→month_from→day_from→[month_to→day_to]→confirm
│   ├── list_subscriptions.py # /my, list_subs callback, del_sub callback
│   ├── start.py              # /start, /help
│   └── admin.py              # /stats (IsAdmin filter applied at router level)
└── scheduler.py         # APScheduler AsyncIOScheduler, interval=CHECK_INTERVAL_HOURS
```

## Key patterns

**Dependency injection** — `RyanairClient` and `Notifier` are created once in `__main__.py` and injected via `dp.start_polling(bot, ryanair_client=client, notifier=notifier)`. Handlers declare them as typed parameters.

**DB session** — `DbSessionMiddleware` injects `session: AsyncSession` via `data["session"]`; handlers declare it as a parameter. Background jobs open sessions directly via `AsyncSessionFactory`.

**FSM airport search** — states `AddSub.origin` / `AddSub.destination` handle both `Message` (text query → show airport buttons, stay in state) and `CallbackQuery` (airport selected → advance). Callback data format: `airport_{purpose}:{IATA}`.

**Date picker** — `month_from` / `month_to` states call `cheapestPerDay` on month selection; available days are cached in FSM state (`available_from`, `available_to`) to avoid a second API call when building `days_kb`. Callback format: `month_{purpose}:{YYYY-MM}`, `day_{purpose}:{YYYY-MM-DD}`.

**Price check job** — `run_check` deduplicates API calls across subscriptions by caching `(origin, dest, YYYY-MM) → MonthlyFares` within one job run. Alerts fire only on `new_price < best_price` (first check establishes baseline without alerting).

## Ryanair API

Unofficial, no key required:
- Fares: `GET https://services-api.ryanair.com/farfnd/3/oneWayFares/{origin}/{dest}/cheapestPerDay?outboundMonthOfDate=YYYY-MM-01&currency=EUR`
- Airports: `GET https://www.ryanair.com/api/views/locate/5/airports/en/active` — field is `code` (not `iataCode`)
- Routes: `GET https://www.ryanair.com/api/views/locate/searchWidget/routes/en/airport/{origin}`

## Git

Commit every meaningful change. Remote: `https://github.com/teohchik/Ryanair-checker.git`
