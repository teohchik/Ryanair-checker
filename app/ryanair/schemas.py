from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class AvailabilityFare(BaseModel):
    amount: Decimal
    count: int


class AvailabilityFlight(BaseModel):
    fares: list[AvailabilityFare]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AvailabilityFlight":
        fares: list[AvailabilityFare] = []
        for fare_group_key in ("regularFare", "businessFare"):
            fare_group = data.get(fare_group_key)
            if fare_group:
                for f in fare_group.get("fares", []):
                    if f.get("amount") is not None and f.get("count") is not None:
                        fares.append(AvailabilityFare(amount=f["amount"], count=f["count"]))
        return cls(fares=fares)


class AvailabilityResponse(BaseModel):
    flights: list[AvailabilityFlight]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AvailabilityResponse":
        flights: list[AvailabilityFlight] = []
        for trip in data.get("trips", []):
            for day in trip.get("dates", []):
                for flight in day.get("flights", []):
                    flights.append(AvailabilityFlight.from_api(flight))
        return cls(flights=flights)

    def cheapest_seats_left(self) -> int | None:
        best_amount: Decimal | None = None
        best_count: int | None = None
        for flight in self.flights:
            for fare in flight.fares:
                if best_amount is None or fare.amount < best_amount:
                    best_amount = fare.amount
                    best_count = fare.count
        return best_count


class FarePrice(BaseModel):
    value: Decimal
    currency_code: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "FarePrice":
        return cls(value=data["value"], currency_code=data["currencyCode"])


class Fare(BaseModel):
    day: date
    price: FarePrice | None
    sold_out: bool = False
    unavailable: bool = False

    @property
    def is_available(self) -> bool:
        return not self.sold_out and not self.unavailable and self.price is not None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Fare":
        price = None
        if data.get("price") is not None and data["price"].get("value") is not None:
            price = FarePrice.from_api(data["price"])
        return cls(
            day=date.fromisoformat(data["day"]),
            price=price,
            sold_out=data.get("soldOut", False),
            unavailable=data.get("unavailable", False),
        )


class MonthlyFares(BaseModel):
    fares: list[Fare]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "MonthlyFares":
        raw_fares = data.get("outbound", {}).get("fares", [])
        return cls(fares=[Fare.from_api(f) for f in raw_fares])

    def available_in_range(self, date_from: date, date_to: date) -> list[Fare]:
        return [
            f for f in self.fares
            if f.is_available and date_from <= f.day <= date_to
        ]
