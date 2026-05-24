from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


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
