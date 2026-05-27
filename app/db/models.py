import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DateMode(enum.Enum):
    SPECIFIC_DAY = "SPECIFIC_DAY"
    DATE_RANGE = "DATE_RANGE"


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(128))
    language_code: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_sub_active_route", "is_active", "origin_iata", "destination_iata"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    origin_iata: Mapped[str] = mapped_column(String(3))
    destination_iata: Mapped[str] = mapped_column(String(3))
    mode: Mapped[DateMode] = mapped_column(Enum(DateMode))
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    best_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    best_price_date: Mapped[date | None] = mapped_column(Date)
    best_price_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    best_price_seats_left: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    snapshots: Mapped[list["PriceSnapshot"]] = relationship(back_populates="subscription")


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (
        Index("ix_snapshot_sub_checked", "subscription_id", "checked_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(Integer, ForeignKey("subscriptions.id"))
    checked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    min_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    min_price_date: Mapped[date | None] = mapped_column(Date)
    available_count: Mapped[int] = mapped_column(Integer, default=0)

    subscription: Mapped["Subscription"] = relationship(back_populates="snapshots")
