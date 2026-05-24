from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.ryanair.client import RyanairClient

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Airport:
    code: str
    name: str
    city: str
    country: str

    def display(self) -> str:
        return f"{self.code} — {self.name}, {self.country}"


_airports: dict[str, Airport] = {}


async def load_airports(client: "RyanairClient") -> None:
    try:
        data = await client.get_active_airports()
        global _airports
        _airports = {
            a["code"]: Airport(
                code=a["code"],
                name=a.get("name", a["code"]),
                city=a.get("city", {}).get("name", ""),
                country=a.get("country", {}).get("name", ""),
            )
            for a in data
            if "code" in a
        }
        log.info("airports_loaded", count=len(_airports))
    except Exception as exc:
        log.error("airports_load_failed", error=str(exc))


def search(query: str, limit: int = 8) -> list[Airport]:
    if not query or not _airports:
        return []
    q = query.strip().upper()
    q_lower = q.lower()

    seen: set[str] = set()
    results: list[Airport] = []

    def _add(airport: Airport) -> bool:
        if airport.code not in seen and len(results) < limit:
            seen.add(airport.code)
            results.append(airport)
            return True
        return False

    # 1. Exact IATA code
    if q in _airports:
        _add(_airports[q])

    # 2. Prefix matches — code, name, city
    for a in _airports.values():
        if len(results) >= limit:
            break
        if (
            a.code.startswith(q)
            or a.name.lower().startswith(q_lower)
            or a.city.lower().startswith(q_lower)
        ):
            _add(a)

    # 3. Substring matches — name, city
    for a in _airports.values():
        if len(results) >= limit:
            break
        if q_lower in a.name.lower() or q_lower in a.city.lower():
            _add(a)

    return results


def get_airport(code: str) -> Airport | None:
    return _airports.get(code.upper())


def is_loaded() -> bool:
    return bool(_airports)
