import asyncio
from datetime import date, datetime
from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.ryanair.schemas import AvailabilityResponse, MonthlyFares

log = structlog.get_logger(__name__)

_BASE = "https://services-api.ryanair.com/farfnd/3"
_LOCATE_BASE = "https://www.ryanair.com/api/views/locate"
_BOOKING_BASE = "https://www.ryanair.com/api/booking/v4/en-ie"
_RYANAIR_BASE = "https://www.ryanair.com"

# Headers that make Ryanair's booking API respond (discovered via HAR analysis)
_BOOKING_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "client": "desktop",
    "client-version": "3.199.1",
    "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


_BOOKING_SESSION_TTL = 1800  # 30 minutes — reuse warmed session within a check cycle


class RyanairClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(headers=_HEADERS, timeout=20.0)
        self._booking_client: httpx.AsyncClient | None = None
        self._booking_warmed_at: datetime | None = None

    async def aclose(self) -> None:
        await self._client.aclose()
        if self._booking_client:
            await self._booking_client.aclose()
            self._booking_client = None

    async def _get_booking_client(self) -> httpx.AsyncClient:
        """Return a warmed booking client, re-warming only if session is older than TTL."""
        now = datetime.utcnow()
        age = (now - self._booking_warmed_at).total_seconds() if self._booking_warmed_at else None
        needs_warmup = self._booking_client is None or age is None or age > _BOOKING_SESSION_TTL

        if needs_warmup:
            if self._booking_client is not None:
                await self._booking_client.aclose()
            self._booking_client = httpx.AsyncClient(
                headers=_BOOKING_HEADERS, timeout=20.0, follow_redirects=True
            )
            # Any valid Ryanair search page sets the session cookies we need
            await self._booking_client.get(
                f"{_RYANAIR_BASE}/ie/en/trip/flights/select",
                params={
                    "adults": 1, "teens": 0, "children": 0, "infants": 0,
                    "dateOut": "", "dateIn": "", "isConnectedFlight": "false",
                    "discount": 0, "promoCode": "", "isReturn": "false",
                },
                headers={"Accept": "text/html,application/xhtml+xml,*/*"},
            )
            self._booking_warmed_at = now
            log.info("booking_session_warmed")

        return self._booking_client  # type: ignore[return-value]

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        reraise=True,
    )
    async def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = await self._client.get(url, params=params or {})
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "30"))
            log.warning("ryanair_rate_limited", retry_after=retry_after)
            await asyncio.sleep(retry_after)
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.json()

    async def get_cheapest_per_day(
        self,
        origin: str,
        destination: str,
        year_month: date,
        currency: str = "EUR",
    ) -> MonthlyFares:
        url = f"{_BASE}/oneWayFares/{origin}/{destination}/cheapestPerDay"
        data = await self._get_json(
            url,
            params={"outboundMonthOfDate": year_month.strftime("%Y-%m-01"), "currency": currency},
        )
        return MonthlyFares.from_api(data)

    async def get_seats_left(
        self,
        origin: str,
        destination: str,
        day: date,
    ) -> int | None:
        """Return seats left at cheapest price for given flight date, or None on failure."""
        date_str = day.strftime("%Y-%m-%d")
        referer = (
            f"{_RYANAIR_BASE}/ie/en/trip/flights/select"
            f"?adults=1&teens=0&children=0&infants=0"
            f"&dateOut={date_str}&dateIn=&isConnectedFlight=false"
            f"&discount=0&promoCode=&isReturn=false"
            f"&originIata={origin}&destinationIata={destination}"
        )
        try:
            client = await self._get_booking_client()
            resp = await client.get(
                f"{_BOOKING_BASE}/availability",
                params={
                    "ADT": 1, "TEEN": 0, "CHD": 0, "INF": 0,
                    "Origin": origin, "Destination": destination,
                    "promoCode": "", "IncludeConnectingFlights": "false",
                    "DateOut": date_str, "DateIn": "",
                    "FlexDaysBeforeOut": 0, "FlexDaysOut": 0,
                    "FlexDaysBeforeIn": 0, "FlexDaysIn": 0,
                    "RoundTrip": "false", "IncludePrimeFares": "false",
                    "ToUs": "AGREED",
                },
                headers={"Referer": referer},
            )
            resp.raise_for_status()
            return AvailabilityResponse.from_api(resp.json()).cheapest_seats_left()
        except Exception as exc:
            log.warning(
                "seats_left_fetch_failed",
                origin=origin, dest=destination, day=date_str, error=str(exc),
            )
            # Invalidate session so next call triggers a fresh warmup
            self._booking_warmed_at = None
            return None

    async def get_active_airports(self) -> list[dict[str, Any]]:
        return await self._get_json(f"{_LOCATE_BASE}/5/airports/en/active")

    async def get_routes_from(self, origin: str) -> set[str]:
        try:
            data = await self._get_json(
                f"{_LOCATE_BASE}/searchWidget/routes/en/airport/{origin}"
            )
            return {r["arrivalAirport"]["code"] for r in data}
        except Exception as exc:
            log.warning("routes_fetch_failed", origin=origin, error=str(exc))
            return set()
