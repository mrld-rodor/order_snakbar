from decimal import Decimal

from app.db import db
from app.models import DiningTable, MenuCategory, MenuProduct, Order, OrderItem


OPEN_ORDER_STATUSES = {"aberto", "confirmado", "preparando", "pronto", "entregue"}


def _active_categories_with_products():
    categories = (
        MenuCategory.query.filter_by(active=True)
        .order_by(MenuCategory.display_order.asc(), MenuCategory.name.asc())
        .all()
    )
    payload = []
    for category in categories:
        products = [
            product.to_dict()
            for product in sorted(category.products, key=lambda item: item.name.lower())
            if product.active
        ]
        payload.append(
            {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "description": category.description,
                "products": products,
            }
        )
    return payload


def _current_open_order_for_table(table_id):
    return (
        Order.query.filter(
            Order.table_id == table_id,
            Order.status.in_(tuple(OPEN_ORDER_STATUSES)),
        )
        .order_by(Order.opened_at.desc())
        .first()
    )


def _table_status_payload(table):
    open_order = _current_open_order_for_table(table.id)
    return {
        "id": table.id,
        "number": table.number,
        "seats": table.seats,
        "active": table.active,
        "has_open_ticket": open_order is not None,
        "ticket": open_order.to_dict() if open_order else None,
    }


def get_collaborator_ordering_bootstrap(collaborator):
    tables = DiningTable.query.filter_by(active=True).order_by(DiningTable.number.asc()).all()
    return {
        "user": collaborator.to_public_dict(),
        "categories": _active_categories_with_products(),
        "tables": [_table_status_payload(table) for table in tables],
    }


def get_table_ticket(table_id):
    table = DiningTable.query.filter_by(id=table_id, active=True).first_or_404()
    ticket = _current_open_order_for_table(table.id)
    return {
        "table": table.to_dict(),
        "ticket": ticket.to_dict() if ticket else None,
    }


def add_product_to_table_ticket(collaborator, table_id, product_id, quantity=1):
    table = DiningTable.query.filter_by(id=table_id, active=True).first()
    if table is None:
        return None, {"table": "Mesa invalida ou inativa."}

    product = MenuProduct.query.filter_by(id=product_id, active=True).first()
    if product is None:
        return None, {"product": "Produto invalido ou inativo."}
    if product.stock_status == "out_of_stock":
        return None, {"product": "Produto sem estoque disponivel no momento."}

    try:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return None, {"quantity": "Quantidade invalida. Informe um inteiro maior que zero."}

    ticket = _current_open_order_for_table(table.id)
    if ticket is None:
        ticket = Order(
            table=table,
            collaborator=collaborator,
            status="aberto",
            notes="Pedido iniciado pelo painel do colaborador.",
        )
        db.session.add(ticket)
        db.session.flush()

    existing_item = next((item for item in ticket.items if item.product_id == product.id), None)
    unit_price = Decimal(product.price)

    if existing_item is None:
        line_total = (unit_price * quantity).quantize(Decimal("0.01"))
        db.session.add(
            OrderItem(
                order=ticket,
                product=product,
                product_name_snapshot=product.name,
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )
    else:
        existing_item.quantity += quantity
        existing_item.line_total = (Decimal(existing_item.unit_price) * existing_item.quantity).quantize(
            Decimal("0.01")
        )

    db.session.flush()
    ticket.recalculate_total()
    db.session.commit()
    return ticket.to_dict(), None