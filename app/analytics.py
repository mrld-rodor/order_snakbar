from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import or_

from app.models import Collaborator, MenuCategory, MenuProduct, Order


OPEN_ORDER_STATUSES = ("aberto", "confirmado", "preparando", "pronto", "entregue")


STAFF_ROLES = ("colaborador", "chefe_sala")


def normalize_period(period):
    period = (period or "day").lower()
    if period not in {"day", "week", "month", "period", "year"}:
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
    elif period == "month":
        start = reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "period":
        start = (reference - timedelta(days=89)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start = reference.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    return start, reference


def _series_bucket_key(period, reference):
    reference = reference.astimezone(timezone.utc)
    period = normalize_period(period)
    if period == "day":
        return reference.strftime("%Y-%m-%d %H"), reference.strftime("%Hh")
    if period == "week":
        return reference.strftime("%Y-%m-%d"), reference.strftime("%a")
    if period == "month":
        return reference.strftime("%Y-%m-%d"), reference.strftime("%d/%m")
    if period == "period":
        week_number = reference.isocalendar().week
        return f"{reference.year}-{week_number:02d}", f"S{week_number:02d}"
    return reference.strftime("%Y-%m"), reference.strftime("%b")


def _sales_trend(period, orders):
    buckets = defaultdict(lambda: {"label": "", "sales_total": Decimal("0.00"), "orders": 0})
    for order in orders:
        reference = (order.closed_at or order.opened_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        key, label = _series_bucket_key(period, reference)
        bucket = buckets[key]
        bucket["label"] = label
        bucket["sales_total"] += Decimal(order.total)
        bucket["orders"] += 1

    trend = []
    for key, bucket in sorted(buckets.items()):
        trend.append(
            {
                "key": key,
                "label": bucket["label"],
                "sales_total": float(bucket["sales_total"]),
                "orders": bucket["orders"],
            }
        )
    return trend


def _build_sales_indicators(period, sales, ranking, orders):
    sales_total = Decimal(str(sales["sales_total"]))
    orders_paid = sales["orders_paid"]
    items_sold = sales["items_sold"]
    average_items = round(items_sold / orders_paid, 1) if orders_paid else 0
    active_days = len({(order.closed_at or order.opened_at).astimezone(timezone.utc).date() for order in orders if (order.closed_at or order.opened_at)})
    average_daily_sales = float((sales_total / active_days).quantize(Decimal("0.01"))) if active_days else 0.0
    average_order_value = float((sales_total / orders_paid).quantize(Decimal("0.01"))) if orders_paid else 0.0

    top_product = ranking[0] if ranking else None
    top_product_share = round((top_product["revenue"] / float(sales_total)) * 100, 1) if top_product and sales_total > 0 else 0

    payment_totals = sorted(sales["payment_mix"], key=lambda item: item["amount"], reverse=True)
    leading_payment = payment_totals[0] if payment_totals else None

    return [
        {
            "label": "Faturamento total",
            "value": float(sales_total),
            "format": "currency",
            "hint": f"Total fechado no {normalize_period(period)}.",
        },
        {
            "label": "Pedidos pagos",
            "value": orders_paid,
            "format": "number",
            "hint": "Volume real de contas encerradas.",
        },
        {
            "label": "Ticket medio",
            "value": average_order_value,
            "format": "currency",
            "hint": "Media de receita por pedido fechado.",
        },
        {
            "label": "Itens por pedido",
            "value": average_items,
            "format": "decimal",
            "hint": "Media de quantidade por conta.",
        },
        {
            "label": "Faturamento medio por dia",
            "value": average_daily_sales,
            "format": "currency",
            "hint": "Ritmo medio considerando dias com vendas.",
        },
        {
            "label": "Peso do produto lider",
            "value": top_product_share,
            "format": "percent",
            "hint": top_product["product"] if top_product else "Sem produto lider no periodo.",
        },
        {
            "label": "Metodo lider",
            "value": leading_payment["amount"] if leading_payment else 0,
            "format": "currency",
            "hint": leading_payment["method"] if leading_payment else "Sem pagamentos fechados.",
        },
    ]


def _sales_highlights(period, ranking, sales, orders):
    top_product = ranking[0] if ranking else None
    top_categories = defaultdict(lambda: {"category": "Sem categoria", "quantity": 0, "revenue": Decimal("0.00")})
    hourly_volume = defaultdict(int)

    for order in orders:
        if order.opened_at:
            hourly_volume[order.opened_at.astimezone(timezone.utc).hour] += 1
        for item in order.items:
            category_name = item.product.category.name if item.product and item.product.category else "Sem categoria"
            entry = top_categories[category_name]
            entry["category"] = category_name
            entry["quantity"] += item.quantity
            entry["revenue"] += Decimal(item.line_total)

    best_category = None
    if top_categories:
        best_category = sorted(top_categories.values(), key=lambda item: (item["revenue"], item["quantity"]), reverse=True)[0]

    busiest_hour = None
    if hourly_volume:
        hour, volume = sorted(hourly_volume.items(), key=lambda item: (item[1], -item[0]), reverse=True)[0]
        busiest_hour = {"label": f"{hour:02d}h", "orders": volume}

    return {
        "top_product": top_product,
        "best_category": {
            "category": best_category["category"],
            "quantity": best_category["quantity"],
            "revenue": float(best_category["revenue"]),
        } if best_category else None,
        "busiest_hour": busiest_hour,
        "payment_mix": sales["payment_mix"],
        "sales_trend": _sales_trend(period, orders),
    }


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


def _service_orders(period, collaborator_id):
    start, end = period_bounds(period)
    return (
        Order.query.filter(Order.collaborator_id == collaborator_id)
        .filter(
            or_(
                Order.opened_at.between(start, end),
                Order.closed_at.between(start, end),
            )
        )
        .order_by(Order.opened_at.desc())
        .all()
    )


def _order_duration_minutes(order):
    if not order.opened_at or not order.closed_at:
        return None
    return round((order.closed_at - order.opened_at).total_seconds() / 60, 1)


def _format_timestamp(value):
    if value is None:
        return None
    return value.astimezone(timezone.utc).strftime("%d/%m %H:%M")


def _build_collaborator_profile(period, collaborator):
    paid_orders = _paid_orders(period, collaborator_id=collaborator.id)
    service_orders = _service_orders(period, collaborator.id)
    now = datetime.now(timezone.utc)

    paid_sales_total = Decimal("0.00")
    total_items_paid = 0
    total_discount = Decimal("0.00")
    durations = []
    paid_tables = set()
    all_tables = set()
    open_orders_count = 0
    open_age_minutes = []
    discounted_orders = 0
    table_metrics = {}
    hourly_flow = {hour: 0 for hour in range(24)}
    daily_trend = defaultdict(lambda: {"label": "", "orders": 0, "sales_total": Decimal("0.00")})
    top_products = {}
    status_mix = {"Pagos": 0, "Abertos": 0, "Em preparo": 0, "Entregues": 0}

    for order in service_orders:
        table_number = order.table.number if order.table else order.table_id
        if table_number is not None:
            all_tables.add(table_number)

        if order.opened_at:
            hourly_flow[order.opened_at.astimezone(timezone.utc).hour] += 1

        if order.status == "pago":
            status_mix["Pagos"] += 1
        elif order.status == "entregue":
            status_mix["Entregues"] += 1
        elif order.status == "aberto":
            status_mix["Abertos"] += 1
        else:
            status_mix["Em preparo"] += 1

        if order.status != "pago":
            open_orders_count += 1
            if order.opened_at:
                open_age_minutes.append(round((now - order.opened_at).total_seconds() / 60, 1))

    for order in paid_orders:
        paid_sales_total += Decimal(order.total)
        total_discount += Decimal(order.discount_amount or 0)
        order_items = sum(item.quantity for item in order.items)
        total_items_paid += order_items

        if Decimal(order.discount_amount or 0) > 0:
            discounted_orders += 1

        duration_minutes = _order_duration_minutes(order)
        if duration_minutes is not None:
            durations.append(duration_minutes)

        table_number = order.table.number if order.table else order.table_id
        if table_number is not None:
            paid_tables.add(table_number)
            entry = table_metrics.setdefault(
                table_number,
                {
                    "table_number": table_number,
                    "orders_count": 0,
                    "sales_total": Decimal("0.00"),
                    "items_sold": 0,
                    "duration_sum": 0.0,
                    "duration_count": 0,
                },
            )
            entry["orders_count"] += 1
            entry["sales_total"] += Decimal(order.total)
            entry["items_sold"] += order_items
            if duration_minutes is not None:
                entry["duration_sum"] += duration_minutes
                entry["duration_count"] += 1

        reference = (order.closed_at or order.opened_at or now).astimezone(timezone.utc)
        trend_key = reference.strftime("%Y-%m-%d")
        daily_trend_entry = daily_trend[trend_key]
        daily_trend_entry["label"] = reference.strftime("%d/%m")
        daily_trend_entry["orders"] += 1
        daily_trend_entry["sales_total"] += Decimal(order.total)

        for item in order.items:
            product_entry = top_products.setdefault(
                item.product_name_snapshot,
                {
                    "product": item.product_name_snapshot,
                    "quantity": 0,
                    "revenue": Decimal("0.00"),
                },
            )
            product_entry["quantity"] += item.quantity
            product_entry["revenue"] += Decimal(item.line_total)

    orders_paid = len(paid_orders)
    avg_items = round(total_items_paid / orders_paid, 1) if orders_paid else 0
    avg_duration = round(sum(durations) / len(durations), 1) if durations else 0
    avg_orders_per_table = round(orders_paid / len(paid_tables), 1) if paid_tables else 0
    avg_revenue_per_table = (
        float((paid_sales_total / len(paid_tables)).quantize(Decimal("0.01"))) if paid_tables else 0.0
    )
    avg_discount = float((total_discount / orders_paid).quantize(Decimal("0.01"))) if orders_paid else 0.0
    avg_open_age = round(sum(open_age_minutes) / len(open_age_minutes), 1) if open_age_minutes else 0

    if avg_duration and avg_duration <= 18:
        service_rhythm = "Agil"
    elif avg_duration and avg_duration <= 28:
        service_rhythm = "Constante"
    elif orders_paid:
        service_rhythm = "Mais demorado"
    else:
        service_rhythm = "Sem base ainda"

    if orders_paid >= 12:
        sales_profile = "Volume forte"
    elif orders_paid >= 6:
        sales_profile = "Volume estavel"
    elif orders_paid:
        sales_profile = "Volume moderado"
    else:
        sales_profile = "Sem fechamentos"

    table_performance = []
    for item in table_metrics.values():
        avg_table_duration = round(item["duration_sum"] / item["duration_count"], 1) if item["duration_count"] else 0
        avg_table_ticket = item["sales_total"] / item["orders_count"] if item["orders_count"] else Decimal("0.00")
        table_performance.append(
            {
                "table_number": item["table_number"],
                "orders_count": item["orders_count"],
                "sales_total": float(item["sales_total"]),
                "avg_ticket": float(avg_table_ticket.quantize(Decimal("0.01"))),
                "avg_duration_minutes": avg_table_duration,
                "items_sold": item["items_sold"],
            }
        )
    table_performance.sort(key=lambda item: (item["sales_total"], item["orders_count"]), reverse=True)

    product_ranking = []
    for item in top_products.values():
        product_ranking.append(
            {
                "product": item["product"],
                "quantity": item["quantity"],
                "revenue": float(item["revenue"]),
            }
        )
    product_ranking.sort(key=lambda item: (item["quantity"], item["revenue"]), reverse=True)

    activity_log = []
    for order in service_orders[:10]:
        item_count = sum(item.quantity for item in order.items)
        duration_minutes = _order_duration_minutes(order)
        if duration_minutes is None and order.opened_at and order.status != "pago":
            duration_minutes = round((now - order.opened_at).total_seconds() / 60, 1)

        activity_log.append(
            {
                "order_id": order.id,
                "table_number": order.table.number if order.table else order.table_id,
                "status": order.status,
                "opened_at": _format_timestamp(order.opened_at),
                "closed_at": _format_timestamp(order.closed_at),
                "duration_minutes": duration_minutes,
                "items_count": item_count,
                "total": float(order.total),
                "discount_amount": float(order.discount_amount),
                "payment_method": order.payment.method if order.payment else None,
            }
        )

    return {
        "collaborator": collaborator.to_public_dict(),
        "headline": f"Perfil operacional de {collaborator.name}",
        "summary": (
            f"{collaborator.name} fechou {orders_paid} pedidos no periodo, atendeu {len(all_tables)} mesas "
            f"e manteve um ritmo {service_rhythm.lower()} de atendimento."
            if orders_paid
            else f"{collaborator.name} ainda nao fechou pedidos neste periodo, mas o painel continua a mostrar mesas em aberto e atividade recente."
        ),
        "badges": [service_rhythm, sales_profile],
        "indicators": {
            "tables_served": len(all_tables),
            "paid_tables": len(paid_tables),
            "avg_orders_per_table": avg_orders_per_table,
            "avg_items_per_order": avg_items,
            "avg_duration_minutes": avg_duration,
            "shortest_service_minutes": min(durations) if durations else 0,
            "longest_service_minutes": max(durations) if durations else 0,
            "avg_revenue_per_table": avg_revenue_per_table,
            "discounted_orders": discounted_orders,
            "avg_discount": avg_discount,
            "open_orders_count": open_orders_count,
            "avg_open_age_minutes": avg_open_age,
        },
        "status_mix": [
            {"label": label, "value": value}
            for label, value in status_mix.items()
            if value > 0
        ],
        "hourly_flow": [
            {"hour": hour, "label": f"{hour:02d}h", "orders": hourly_flow[hour]}
            for hour in range(24)
        ],
        "daily_trend": [
            {
                "label": item["label"],
                "orders": item["orders"],
                "sales_total": float(item["sales_total"]),
            }
            for _, item in sorted(daily_trend.items())
        ],
        "table_performance": table_performance[:6],
        "top_products": product_ranking[:5],
        "activity_log": activity_log,
    }


def get_collaborator_rankings(period):
    collaborators = [
        collaborator
        for collaborator in Collaborator.query.filter(
            Collaborator.role.in_(STAFF_ROLES),
            Collaborator.active.is_(True),
        )
        .order_by(Collaborator.name.asc())
        .all()
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
    paid_orders = _paid_orders(period)
    open_orders = (
        Order.query.filter(Order.status.in_(OPEN_ORDER_STATUSES))
        .order_by(Order.opened_at.desc())
        .all()
    )
    return {
        "period": normalize_period(period),
        "sales": sales,
        "sales_indicators": _build_sales_indicators(period, sales, ranking, paid_orders),
        "sales_highlights": _sales_highlights(period, ranking, sales, paid_orders),
        "inventory": inventory,
        "top_products": ranking[:8],
        "category_stock": inventory["categories"],
        "open_tables": [order.to_dict() for order in open_orders[:8]],
        "recent_orders": get_recent_orders(limit=8),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_collaborators_list():
    collaborators = (
        Collaborator.query.filter(
            Collaborator.role.in_(STAFF_ROLES),
            Collaborator.active.is_(True),
        )
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
        "selected_profile": _build_collaborator_profile(period, selected) if selected is not None else None,
        "ranking": ranking,
        "collaborators": get_collaborators_list(),
        "open_orders": [order.to_dict() for order in open_orders[:8]],
        "open_orders_count": len(open_orders),
        "recent_orders": recent_orders,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_admin_dashboard():
    collaborators = (
        Collaborator.query.filter(
            Collaborator.role.in_(STAFF_ROLES),
            Collaborator.active.is_(True),
        ).count()
    )
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