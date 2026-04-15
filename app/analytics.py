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


def get_inventory_overview():
    products = MenuProduct.query.order_by(MenuProduct.name.asc()).all()
    total_units = sum(product.stock_quantity for product in products)
    low_stock_products = [product for product in products if product.stock_status == "low_stock"]
    out_of_stock_products = [product for product in products if product.stock_status == "out_of_stock"]
    stock_value = sum(Decimal(product.price) * product.stock_quantity for product in products)

    categories = []
    for category in MenuCategory.query.order_by(MenuCategory.display_order.asc()).all():
        category_products = list(category.products)
        categories.append(
            {
                "category": category.name,
                "product_count": len(category_products),
                "stock_units": sum(product.stock_quantity for product in category_products),
                "stock_value": float(
                    sum(Decimal(product.price) * product.stock_quantity for product in category_products)
                ),
            }
        )

    return {
        "total_products": len(products),
        "active_products": len([product for product in products if product.active]),
        "total_units": total_units,
        "stock_value": float(stock_value.quantize(Decimal("0.01"))) if products else 0.0,
        "low_stock_count": len(low_stock_products),
        "out_of_stock_count": len(out_of_stock_products),
        "low_stock_products": [product.to_dict() for product in low_stock_products],
        "out_of_stock_products": [product.to_dict() for product in out_of_stock_products],
        "categories": categories,
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


def get_product_rankings(period):
    orders = _paid_orders(period)
    products = {}

    for order in orders:
        for item in order.items:
            product = item.product
            entry = products.setdefault(
                item.product_id,
                {
                    "product_id": item.product_id,
                    "product": item.product_name_snapshot,
                    "category": product.category.name if product and product.category else None,
                    "quantity": 0,
                    "revenue": Decimal("0.00"),
                    "stock_quantity": product.stock_quantity if product else 0,
                    "stock_status": product.stock_status if product else "unknown",
                },
            )
            entry["quantity"] += item.quantity
            entry["revenue"] += Decimal(item.line_total)

    ranking = []
    for item in products.values():
        ranking.append({**item, "revenue": float(item["revenue"])})

    ranking.sort(key=lambda item: (item["revenue"], item["quantity"]), reverse=True)
    return ranking


def get_product_dashboard(period):
    sales = get_sales_summary(period)
    inventory = get_inventory_overview()
    ranking = get_product_rankings(period)
    return {
        "period": normalize_period(period),
        "sales": sales,
        "inventory": inventory,
        "top_products": ranking[:8],
        "category_stock": inventory["categories"],
        "recent_orders": get_recent_orders(limit=8),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_collaborators_list():
    collaborators = (
        Collaborator.query.filter_by(role="colaborador", active=True)
        .order_by(Collaborator.name.asc())
        .all()
    )
    return [collaborator.to_public_dict() for collaborator in collaborators]


def get_collaborator_admin_dashboard(period, collaborator_id=None):
    ranking = get_collaborator_rankings(period)
    selected = Collaborator.query.get(collaborator_id) if collaborator_id is not None else None

    open_orders_query = Order.query.filter(Order.status != "pago")
    if collaborator_id is not None:
        open_orders_query = open_orders_query.filter(Order.collaborator_id == collaborator_id)
    open_orders = open_orders_query.order_by(Order.opened_at.desc()).all()

    if selected is not None:
        summary = get_sales_summary(period, selected.id)
        recent_orders = get_recent_orders(limit=8, collaborator_id=selected.id)
        selected_payload = selected.to_public_dict()
    else:
        summary = get_sales_summary(period)
        recent_orders = get_recent_orders(limit=10)
        selected_payload = None

    return {
        "period": normalize_period(period),
        "selected_collaborator": selected_payload,
        "summary": summary,
        "ranking": ranking,
        "collaborators": get_collaborators_list(),
        "open_orders": [order.to_dict() for order in open_orders[:8]],
        "open_orders_count": len(open_orders),
        "recent_orders": recent_orders,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_admin_dashboard():
    collaborators = Collaborator.query.filter_by(role="colaborador", active=True).count()
    return {
        "message": "Painel administrativo carregado com resumo operacional e comercial.",
        "catalog": get_catalog_overview(),
        "inventory": get_inventory_overview(),
        "overview": {
            "day": get_sales_summary("day"),
            "week": get_sales_summary("week"),
            "month": get_sales_summary("month"),
        },
        "active_collaborators": collaborators,
        "collaborators": get_collaborator_rankings("month"),
        "recent_orders": get_recent_orders(limit=8),
    }