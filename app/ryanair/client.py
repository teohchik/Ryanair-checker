import asyncio
from datetime import date
from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.ryanair.schemas import AvailabilityResponse, MonthlyFares

log = structlog.get_logger(__name__)

_BASE = "https://services-api.ryanair.com/farfnd/3"
_LOCATE_BASE = "https://www.ryanair.com/api/views/locate"
_BOOKING_BASE = "https://www.ryanair.com/api/booking/v4/en-gb"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


class RyanairClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(headers=_HEADERS, timeout=20.0)

    async def aclose(self) -> None:
        await self._client.aclose()

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
        try:
            data = await self._get_json(
                f"{_BOOKING_BASE}/availability",
                params={
                    "ADT": 1, "TEEN": 0, "CHD": 0, "INF": 0,
                    "Origin": origin,
                    "Destination": destination,
                    "DateOut": day.strftime("%Y-%m-%d"),
                    "DateIn": "",
                    "FlexDaysOut": 0,
                    "RoundTrip": "false",
                    "IncludeConnectingFlights": "false",
                    "ToUs": "AGREED",
                },
            )
            return AvailabilityResponse.from_api(data).cheapest_seats_left()
        except Exception as exc:
            log.warning("seats_left_fetch_failed", origin=origin, dest=destination, day=str(day), error=str(exc))
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
