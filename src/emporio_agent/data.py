"""Loads the store CSVs into typed, cleaned records.

The dataset is tiny (65 products, 20 orders), so everything is loaded into
memory once. A database would add setup cost without any benefit here.
"""

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
STORE_TZ = ZoneInfo("America/Campo_Grande")


@dataclass(frozen=True)
class Category:
    id: int
    name: str
    description: str


@dataclass(frozen=True)
class Promotion:
    id: int
    product_id: int
    discount_percent: int
    label: str
    is_active: bool


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    category_id: int
    description: str
    price: float
    stock: int
    status: str  # active | discontinued | coming_soon
    specs: dict = field(hash=False)


@dataclass(frozen=True)
class Customer:
    id: int
    name: str
    phone: str
    email: str
    city: str


@dataclass(frozen=True)
class OrderItem:
    product_id: int
    quantity: int


@dataclass(frozen=True)
class Order:
    id: int
    customer_id: int
    order_date: date
    status: str  # pending | confirmed | shipped | delivered | cancelled
    total: float
    payment_method: str
    tracking_code: str | None
    estimated_delivery: date | None
    notes: str | None
    items: tuple[OrderItem, ...]


@dataclass(frozen=True)
class Store:
    categories: dict[int, Category]
    products: dict[int, Product]
    promotions: list[Promotion]
    customers: dict[int, Customer]
    orders: dict[int, Order]

    def active_promotion(self, product_id: int) -> Promotion | None:
        """Promotions are not cumulative, so at most one applies: the best active one."""
        active = [p for p in self.promotions if p.product_id == product_id and p.is_active]
        return max(active, key=lambda p: p.discount_percent, default=None)


def _read(name: str) -> list[dict[str, str]]:
    with open(DATA_DIR / f"{name}.csv", encoding="utf-8", newline="") as f:
        return [{k: v.strip() for k, v in row.items()} for row in csv.DictReader(f)]


def _date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


@lru_cache(maxsize=1)
def load_store() -> Store:
    categories = {
        int(r["category_id"]): Category(int(r["category_id"]), r["name"], r["description"])
        for r in _read("categories")
    }
    products = {
        int(r["product_id"]): Product(
            id=int(r["product_id"]),
            name=r["name"],
            category_id=int(r["category_id"]),
            description=r["description"],
            price=float(r["price_brl"]),
            stock=int(r["stock_quantity"] or 0),
            status=r["status"],
            specs=json.loads(r["specs"]) if r["specs"] else {},
        )
        for r in _read("products")
    }
    promotions = [
        Promotion(
            id=int(r["promotion_id"]),
            product_id=int(r["product_id"]),
            discount_percent=int(r["discount_percent"]),
            label=r["description"],
            is_active=r["is_active"] == "1",
        )
        for r in _read("promotions")
    ]
    customers = {
        int(r["customer_id"]): Customer(
            int(r["customer_id"]), r["name"], r["phone"], r["email"].lower(), r["city"]
        )
        for r in _read("customers")
    }
    items: dict[int, list[OrderItem]] = {}
    for r in _read("order_items"):
        items.setdefault(int(r["order_id"]), []).append(
            OrderItem(int(r["product_id"]), int(r["quantity"]))
        )
    orders = {
        int(r["order_id"]): Order(
            id=int(r["order_id"]),
            customer_id=int(r["customer_id"]),
            order_date=date.fromisoformat(r["order_date"]),
            status=r["status"],
            total=float(r["total_brl"]),
            payment_method=r["payment_method"],
            tracking_code=r["tracking_code"] or None,
            estimated_delivery=_date(r["estimated_delivery"]),
            notes=r["notes"] or None,
            items=tuple(items.get(int(r["order_id"]), [])),
        )
        for r in _read("orders")
    }
    return Store(categories, products, promotions, customers, orders)


def now() -> datetime:
    """Current time in the store's timezone.

    EMPORIO_NOW (ISO format, e.g. 2026-02-20T10:00) pins the clock so demos
    and tests are reproducible.
    """
    pinned = os.getenv("EMPORIO_NOW")
    if pinned:
        return datetime.fromisoformat(pinned).replace(tzinfo=STORE_TZ)
    return datetime.now(STORE_TZ)
