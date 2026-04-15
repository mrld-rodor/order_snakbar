from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import Collaborator, MenuCategory, MenuProduct, Order


def normalize_period(period):
    period = (period or "day").lower()
    if period not in {"day", "week", "month"}:
        return "day"
    return period


def period_bounds(period, reference=None):
    reference = reference or datetime.now(timezone.utc)
    period = normalize_period(period)

    if period == "day":
        start = reference.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = (reference - timedelta(days=reference.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        start = reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return start, reference


def get_catalog_overview():
    categories = MenuCategory.query.order_by(MenuCategory.display_order.asc()).all()
    products = MenuProduct.query.filter_by(active=True).all()

    return {
        "category_count": len(categories),
        "product_count": len(products),
        "vegan_product_count": len([product for product in products if product.is_vegan]),
        "categories": [category.to_dict(include_products=True) for category in categories],
    }


def get_menu_catalog():
    categories = MenuCategory.query.order_by(MenuCategory.display_order.asc()).all()
    return {"categories": [category.to_dict(include_products=True) for category in categories]}


def _paid_orders(period, collaborator_id=None):
    start, end = period_bounds(period)
    query = Order.query.filter(
        Order.status == "pago",
        Order.closed_at.isnot(None),
        Order.closed_at >= start,
        Order.closed_at <= end,
    ).order_by(Order.closed_at.desc())
    if collaborator_id is not None:
        query = query.filter(Order.collaborator_id == collaborator_id)
    return query.all()


def get_sales_summary(period, collaborator_id=None):
    orders = _paid_orders(period, collaborator_id=collaborator_id)
    sales_total = Decimal("0.00")
    items_sold = 0
    vegan_items_sold = 0
    product_totals = {}
    payment_totals = {}

    for order in orders:
        sales_total += Decimal(order.total)
        for item in order.items:
            items_sold += item.quantity
            if item.product and item.product.is_vegan:
                vegan_items_sold += item.quantity
            product_entry = product_totals.setdefault(
                item.product_name_snapshot,
                {"product": item.product_name_snapshot, "quantity": 0, "revenue": Decimal("0.00")},
            )
            product_entry["quantity"] += item.quantity
            product_entry["revenue"] += Decimal(item.line_total)

        if order.payment:
            payment_entry = payment_totals.setdefault(
                order.payment.method,
                {"method": order.payment.method, "count": 0, "amount": Decimal("0.00")},
            )
            payment_entry["count"] += 1
            payment_entry["amount"] += Decimal(order.payment.amount)

    order_count = len(orders)
    avg_ticket = (sales_total / order_count).quantize(Decimal("0.01")) if order_count else Decimal("0.00")

    top_products = sorted(
        product_totals.values(),
        key=lambda item: (item["quantity"], item["revenue"]),
        reverse=True,
    )[:5]
    payment_mix = sorted(payment_totals.values(), key=lambda item: item["amount"], reverse=True)

    return {
        "period": normalize_period(period),
        "sales_total": float(sales_total),
        "orders_paid": order_count,
        "avg_ticket": float(avg_ticket),
        "items_sold": items_sold,
        "vegan_items_sold": vegan_items_sold,
        "top_products": [
            {"product": item["product"], "quantity": item["quantity"], "revenue": float(item["revenue"])}
            for item in top_products
        ],
        "payment_mix": [
            {"method": item["method"], "count": item["count"], "amount": float(item["amount"])}
            for item in payment_mix
        ],
    }


def get_recent_orders(limit=5, collaborator_id=None):
    query = Order.query.order_by(Order.opened_at.desc())
    if collaborator_id is not None:
        query = query.filter(Order.collaborator_id == collaborator_id)
    orders = query.limit(limit).all()
    return [order.to_dict() for order in orders]


def get_collaborator_rankings(period):
    collaborators = [
        collaborator
        for collaborator in Collaborator.query.filter_by(role="colaborador", active=True).order_by(Collaborator.name.asc()).all()
    ]
    orders = _paid_orders(period)
    metrics = {
        collaborator.id: {
            "collaborator": collaborator.to_public_dict(),
            "sales_total": Decimal("0.00"),
            "orders_paid": 0,
            "items_sold": 0,
        }
        for collaborator in collaborators
    }

    for order in orders:
        collaborator_metrics = metrics.get(order.collaborator_id)
        if not collaborator_metrics:
            continue
        collaborator_metrics["sales_total"] += Decimal(order.total)
        collaborator_metrics["orders_paid"] += 1
        collaborator_metrics["items_sold"] += sum(item.quantity for item in order.items)

    ranking = []
    for item in metrics.values():
        order_count = item["orders_paid"]
        avg_ticket = item["sales_total"] / order_count if order_count else Decimal("0.00")
        ranking.append(
            {
                "collaborator": item["collaborator"],
                "sales_total": float(item["sales_total"]),
                "orders_paid": order_count,
                "items_sold": item["items_sold"],
                "avg_ticket": float(avg_ticket.quantize(Decimal("0.01"))),
            }
        )

    ranking.sort(key=lambda item: (item["sales_total"], item["orders_paid"]), reverse=True)
    return ranking


def get_collaborator_dashboard(collaborator):
    return {
        "message": "Painel do colaborador carregado com dados reais do banco.",
        "user": collaborator.to_public_dict(),
        "overview": {
            "day": get_sales_summary("day", collaborator.id),
            "week": get_sales_summary("week", collaborator.id),
            "month": get_sales_summary("month", collaborator.id),
        },
        "recent_orders": get_recent_orders(limit=6, collaborator_id=collaborator.id),
    }


def get_admin_dashboard():
    collaborators = Collaborator.query.filter_by(role="colaborador", active=True).count()
    return {
        "message": "Painel administrativo carregado com resumo operacional e comercial.",
        "catalog": get_catalog_overview(),
        "overview": {
            "day": get_sales_summary("day"),
            "week": get_sales_summary("week"),
            "month": get_sales_summary("month"),
        },
        "active_collaborators": collaborators,
        "collaborators": get_collaborator_rankings("month"),
        "recent_orders": get_recent_orders(limit=8),
    }