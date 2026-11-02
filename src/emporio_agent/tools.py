"""Deterministic business logic exposed to the LLM as tools.

Guiding principle: the LLM talks, the code computes. Anything that must be
exact (prices, active promotions, installments, deadlines, stock) is
calculated here, so the model only has to phrase the answer.
Every function returns a JSON-serializable dict.
"""

import re
import unicodedata
from datetime import date, datetime, time, timedelta

from .data import Product, Store, load_store, now

PIX_DISCOUNT = 0.05
FREE_SHIPPING_ABOVE = 500.0
LOCAL_SHIPPING_FEE = 35.0
SPLIT_PAYMENT_ABOVE = 2000.0
MAX_INSTALLMENTS = 12

AVAILABILITY = {
    "active": "disponível",
    "out_of_stock": "esgotado",
    "discontinued": "descontinuado",
    "coming_soon": "em breve",
}
ORDER_STATUS = {
    "pending": "aguardando confirmação do pagamento",
    "confirmed": "pagamento confirmado, em preparação",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}

# Opening hours by weekday (Monday = 0). None means closed.
OPENING_HOURS = {
    0: (time(9), time(18)),
    1: (time(9), time(18)),
    2: (time(9), time(18)),
    3: (time(9), time(18)),
    4: (time(9), time(18)),
    5: (time(9), time(13)),
    6: None,
}
# Fixed-date national holidays. Movable ones (Carnival, Good Friday,
# Corpus Christi) are left out on purpose; see docs/suposicoes.md.
HOLIDAYS = {(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25)}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _money(value: float) -> float:
    return round(value, 2)


def _availability(product: Product) -> str:
    if product.status in ("discontinued", "coming_soon"):
        return AVAILABILITY[product.status]
    return AVAILABILITY["active"] if product.stock > 0 else AVAILABILITY["out_of_stock"]


def _can_buy(product: Product) -> bool:
    return product.status == "active" and product.stock > 0


def _final_price(store: Store, product: Product) -> float:
    promo = store.active_promotion(product.id)
    if promo is None:
        return product.price
    return _money(product.price * (1 - promo.discount_percent / 100))


def _product_view(store: Store, product: Product) -> dict:
    promo = store.active_promotion(product.id)
    final = _final_price(store, product)
    return {
        "product_id": product.id,
        "name": product.name,
        "category": store.categories[product.category_id].name,
        "description": product.description,
        "availability": _availability(product),
        "stock_quantity": product.stock,
        "price_original": product.price,
        "promotion": (
            {"label": promo.label, "discount_percent": promo.discount_percent} if promo else None
        ),
        "price_final": final,
        # PIX discount does not stack with promotions (policy 6.2).
        "price_pix": final if promo else _money(product.price * (1 - PIX_DISCOUNT)),
        "specs": product.specs,
    }


def search_products(
    query: str | None = None,
    category: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    only_available: bool = False,
    limit: int = 10,
) -> dict:
    """Searches the catalog. Price filters use the final price (with active promotion)."""
    store = load_store()
    # Short words ("de", "e", "um") only add noise, but short model codes
    # with digits ("7c", "x1") are kept.
    normalized_query = _normalize(query) if query else ""
    terms = [t for t in normalized_query.split() if len(t) >= 3 or any(c.isdigit() for c in t)]
    category_key = _normalize(category) if category else None

    scored = []
    for product in store.products.values():
        category_name = store.categories[product.category_id].name
        if category_key and _normalize(category_name) != category_key:
            continue
        final = _final_price(store, product)
        if max_price is not None and final > max_price:
            continue
        if min_price is not None and final < min_price:
            continue
        if only_available and not _can_buy(product):
            continue
        score = 0
        if terms:
            haystack = _normalize(
                " ".join([product.name, product.description, category_name, *map(str, product.specs.values())])
            )
            words = set(haystack.split())
            score = sum(1 for t in terms if t in words or (len(t) >= 4 and t in haystack))
            # Exact model name ranks first, ignoring spaces ("GD-20" == "GD20").
            if normalized_query.replace(" ", "") in _normalize(product.name).replace(" ", ""):
                score += len(terms) + 1
            if score == 0:
                continue
        scored.append((score, product))

    # Best match first, then products the customer can actually buy, then cheapest.
    scored.sort(key=lambda sp: (-sp[0], not _can_buy(sp[1]), _final_price(store, sp[1])))
    results = [_product_view(store, p) for _, p in scored[:limit]]
    response = {"total_found": len(scored), "returned": len(results), "products": results}
    if not scored:
        response["note"] = "Nenhum produto encontrado no catálogo com esses critérios."
    return response


def _min_installment(n: int) -> float:
    """Policy 3.1: minimum installment depends on the number of installments."""
    if n <= 3:
        return 50.0
    if n <= 6:
        return 80.0
    return 100.0


def payment_options(items: list[dict], city: str | None = None) -> dict:
    """Computes totals for each payment method, valid installments and shipping.

    items: [{"product_id": int, "quantity": int}]
    """
    store = load_store()
    lines, warnings = [], []
    total_final = total_pix = 0.0
    for item in items:
        product = store.products.get(int(item["product_id"]))
        quantity = max(1, int(item.get("quantity", 1)))
        if product is None:
            warnings.append(f"Produto {item['product_id']} não existe no catálogo.")
            continue
        if not _can_buy(product):
            warnings.append(f"{product.name} está {_availability(product)} e não entrou no cálculo.")
            continue
        if quantity > product.stock:
            warnings.append(f"{product.name}: só há {product.stock} unidade(s) em estoque; não entrou no cálculo.")
            continue
        view = _product_view(store, product)
        lines.append({"name": product.name, "quantity": quantity, **{k: view[k] for k in ("price_original", "promotion", "price_final", "price_pix")}})
        total_final += view["price_final"] * quantity
        total_pix += view["price_pix"] * quantity

    total_final, total_pix = _money(total_final), _money(total_pix)
    installments = [
        {"installments": n, "installment_value": _money(total_final / n)}
        for n in range(1, MAX_INSTALLMENTS + 1)
        if total_final > 0 and total_final / n >= _min_installment(n)
    ]
    result = {
        "items": lines,
        "total": total_final,
        "pix": {"total": total_pix, "note": "5% de desconto no PIX, exceto em itens já em promoção."},
        "debit": {"total": total_final},
        "boleto": {"total": total_final, "note": "Compensação em até 3 dias úteis."},
        "credit_card": {
            "max_installments_without_interest": installments[-1]["installments"] if installments else 0,
            "options": installments,
        },
        "split_payment_allowed": total_final > SPLIT_PAYMENT_ABOVE,
        "shipping": _shipping(city, total_final),
    }
    if warnings:
        result["warnings"] = warnings
    return result


def _shipping(city: str | None, total: float) -> dict:
    if not city:
        return {"note": "Informe a cidade para calcular o frete."}
    if _normalize(city) == "campo grande":
        free = total > FREE_SHIPPING_ABOVE
        return {
            "region": "Região metropolitana de Campo Grande",
            "fee": 0.0 if free else LOCAL_SHIPPING_FEE,
            "free": free,
            "deadline": "1 a 3 dias úteis, por motoboy próprio",
        }
    return {
        "region": "Outras cidades",
        "fee": None,
        "note": "Calculado pelo CEP, peso e dimensões (PAC, SEDEX ou Jadlog). Itens grandes podem exigir cotação especial.",
    }


def _payment_label(method: str) -> str:
    if method.startswith("credit_"):
        return f"cartão de crédito em {method.removeprefix('credit_')}"
    return {"pix": "PIX", "debit": "cartão de débito", "boleto": "boleto"}.get(method, method)


def _deadline(start: date, days: int, today: date) -> dict:
    deadline = start + timedelta(days=days)
    return {"deadline": deadline.isoformat(), "within_deadline": today <= deadline}


def get_order(order_id: int, email: str) -> dict:
    """Returns an order only if the e-mail matches the customer who placed it (LGPD)."""
    store = load_store()
    order = store.orders.get(int(order_id))
    customer = store.customers.get(order.customer_id) if order else None
    if order is None or customer is None or customer.email != email.strip().lower():
        # Same message for "not found" and "wrong e-mail", so the tool
        # cannot be used to discover which order numbers exist.
        return {"found": False, "message": "Pedido não encontrado para este número e e-mail."}

    today = now().date()
    result = {
        "found": True,
        "order_id": order.id,
        "customer_first_name": customer.name.split()[0],
        "order_date": order.order_date.isoformat(),
        "status": ORDER_STATUS.get(order.status, order.status),
        "total": order.total,
        "payment_method": _payment_label(order.payment_method),
        "items": [
            {"name": store.products[i.product_id].name, "quantity": i.quantity} for i in order.items
        ],
        "tracking_code": order.tracking_code,
        "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
        "notes": order.notes,
        "today": today.isoformat(),
    }
    if order.status == "shipped" and order.estimated_delivery:
        result["delayed"] = today > order.estimated_delivery
    if order.status == "delivered" and order.estimated_delivery:
        # The data has no actual delivery date; the estimate is used instead.
        delivered = order.estimated_delivery
        result["policy_checks"] = {
            "assumed_delivery_date": delivered.isoformat(),
            "return_or_exchange_7_days_from_delivery": _deadline(delivered, 7, today),
            "defect_exchange_30_days_from_purchase": _deadline(order.order_date, 30, today),
            "legal_warranty_90_days_from_delivery": _deadline(delivered, 90, today),
        }
    return result


def opening_status(moment: datetime | None = None) -> dict:
    """Whether the store is open right now and, if not, when it opens next."""
    moment = moment or now()

    def hours(day: date):
        if (day.month, day.day) in HOLIDAYS:
            return None
        return OPENING_HOURS[day.weekday()]

    today_hours = hours(moment.date())
    is_open = bool(today_hours) and today_hours[0] <= moment.time() < today_hours[1]
    result = {"now": moment.strftime("%Y-%m-%d %H:%M"), "is_open": is_open}
    if is_open:
        result["closes_at"] = today_hours[1].strftime("%H:%M")
        return result
    for offset in range(0, 8):
        day = moment.date() + timedelta(days=offset)
        day_hours = hours(day)
        if day_hours and (offset > 0 or moment.time() < day_hours[0]):
            result["next_opening"] = f"{day.isoformat()} {day_hours[0].strftime('%H:%M')}"
            break
    return result
