"""Business rules from the policy manual, checked against the real data files."""

from datetime import datetime

import pytest

from emporio_agent.data import STORE_TZ, load_store
from emporio_agent.tools import get_order, opening_status, payment_options, search_products


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setenv("EMPORIO_NOW", "2026-11-02T17:00")


def email_of(customer_id: int) -> str:
    return load_store().customers[customer_id].email


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=STORE_TZ)


# --- Catalog -----------------------------------------------------------------

def test_search_by_name_finds_exact_product():
    result = search_products(query="Takamine GD20")
    first = result["products"][0]
    assert first["name"] == "Takamine GD20 Dreadnought Natural"
    assert first["price_final"] == 2199.0


@pytest.mark.parametrize("query", ["takamine gd 20", "GD-20", "gd20"])
def test_model_code_variations_rank_the_right_product_first(query):
    assert search_products(query=query)["products"][0]["product_id"] == 95


def test_price_filter_uses_final_price_and_only_available_products():
    result = search_products(category="violões", max_price=1000, only_available=True)
    assert result["total_found"] > 0
    for product in result["products"]:
        assert product["price_final"] <= 1000
        assert product["availability"] == "disponível"


def test_out_of_stock_and_discontinued_are_flagged_not_hidden():
    names = {p["name"]: p["availability"] for p in search_products(query="Giannini GF-3D")["products"]}
    assert names["Giannini GF-3D Dreadnought Sunburst"] == "esgotado"
    discontinued = search_products(query="Shelby SN-7C")["products"][0]
    assert discontinued["availability"] == "descontinuado"


def test_category_without_products_returns_empty_with_note():
    result = search_products(category="Instrumentos de Sopro (Metais)")
    assert result["total_found"] == 0
    assert "note" in result


# --- Promotions and PIX (policy 6.2) -----------------------------------------

def test_only_active_promotion_is_applied():
    # Product 95 only has an expired promotion.
    product = search_products(query="Takamine GD20")["products"][0]
    assert product["promotion"] is None


def test_active_promotion_shows_original_price_and_discount():
    product = next(p for p in search_products(query="Crafter HT-100")["products"] if p["product_id"] == 90)
    assert product["promotion"] == {"label": "Desconto Exclusivo", "discount_percent": 18}
    assert product["price_original"] == 2399.0
    assert product["price_final"] == 1967.18


def test_pix_discount_does_not_stack_with_promotion():
    promo = payment_options([{"product_id": 90, "quantity": 1}])
    assert promo["pix"]["total"] == promo["total"]
    regular = payment_options([{"product_id": 95, "quantity": 1}])
    assert regular["pix"]["total"] == 2089.05


# --- Installments (policy 3.1) -------------------------------------------------

@pytest.mark.parametrize(
    ("product_id", "price", "max_installments"),
    [
        (83, 429.9, 5),   # 6x would be R$ 71.65 < R$ 80
        (95, 2199.0, 12),
        (119, 159.9, 3),  # 4x would be R$ 39.98 < R$ 80
    ],
)
def test_max_installments_respect_minimum_value(product_id, price, max_installments):
    result = payment_options([{"product_id": product_id, "quantity": 1}])
    assert result["total"] == price
    assert result["credit_card"]["max_installments_without_interest"] == max_installments


def test_split_payment_only_above_2000():
    assert payment_options([{"product_id": 95}])["split_payment_allowed"] is True
    assert payment_options([{"product_id": 83}])["split_payment_allowed"] is False


def test_unavailable_items_are_left_out_with_warning():
    result = payment_options([{"product_id": 96}, {"product_id": 83}])
    assert result["total"] == 429.9
    assert any("esgotado" in w for w in result["warnings"])


# --- Shipping (policy 5.1) -----------------------------------------------------

def test_local_shipping_free_above_500_only():
    assert payment_options([{"product_id": 95}], city="Campo Grande")["shipping"]["fee"] == 0.0
    assert payment_options([{"product_id": 83}], city="campo grande")["shipping"]["fee"] == 35.0
    assert payment_options([{"product_id": 83}], city="Dourados")["shipping"]["fee"] is None


# --- Orders and privacy ------------------------------------------------------------

def test_order_requires_matching_email():
    assert get_order(1, "alguem@outro.com")["found"] is False
    assert get_order(999, email_of(3))["found"] is False
    assert get_order(1, email_of(3).upper())["found"] is True


def test_delivered_order_return_windows():
    checks = get_order(1, email_of(3))["policy_checks"]
    assert checks["assumed_delivery_date"] == "2025-10-25"
    assert checks["regret_return_7_days_from_delivery"]["within_deadline"] is False


def test_return_window_open_right_after_delivery(monkeypatch):
    monkeypatch.setenv("EMPORIO_NOW", "2025-10-30T10:00")
    checks = get_order(1, email_of(3))["policy_checks"]
    assert checks["regret_return_7_days_from_delivery"]["within_deadline"] is True


def test_shipped_order_past_estimate_is_flagged_as_delayed():
    assert get_order(8, email_of(2))["delayed"] is True


def test_cancelled_order_exposes_reason():
    assert get_order(17, email_of(15))["notes"] == "Pedido cancelado pelo cliente antes do processamento"


# --- Opening hours (policy 2) --------------------------------------------------------

@pytest.mark.parametrize(
    ("moment", "is_open", "next_opening"),
    [
        ("2026-11-03T10:00", True, None),               # Tuesday morning
        ("2026-11-03T18:30", False, "2026-11-04 09:00"),  # after closing
        ("2026-11-07T14:00", False, "2026-11-09 09:00"),  # Saturday afternoon
        ("2026-11-02T10:00", False, "2026-11-03 09:00"),  # holiday (Finados)
    ],
)
def test_opening_status(moment, is_open, next_opening):
    status = opening_status(at(moment))
    assert status["is_open"] is is_open
    assert status.get("next_opening") == next_opening
