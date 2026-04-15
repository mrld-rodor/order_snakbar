from decimal import Decimal

from app.db import db
from app.models import DiningTable, MenuCategory, MenuProduct, Order, OrderItem, Payment, utcnow


OPEN_ORDER_STATUSES = {"aberto", "confirmado", "preparando", "pronto", "entregue"}
MANAGER_ROLES = {"administrador", "chefe_sala"}


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


def can_manage_ticket(collaborator, ticket):
    if collaborator is None or ticket is None:
        return False
    if collaborator.role in MANAGER_ROLES:
        return True
    return collaborator.id == ticket.collaborator_id


def _ticket_permissions_payload(collaborator, ticket):
    can_manage = can_manage_ticket(collaborator, ticket)
    return {
        "is_owner": bool(ticket and collaborator and collaborator.id == ticket.collaborator_id),
        "can_manage": can_manage,
        "can_close": can_manage,
    }


def _ticket_payload(ticket, collaborator):
    payload = ticket.to_dict()
    payload["permissions"] = _ticket_permissions_payload(collaborator, ticket)
    return payload


def get_collaborator_ordering_bootstrap(collaborator):
    tables = DiningTable.query.filter_by(active=True).order_by(DiningTable.number.asc()).all()
    return {
        "user": collaborator.to_public_dict(include_pin=True),
        "categories": _active_categories_with_products(),
        "tables": [_table_status_payload(table) for table in tables],
    }


def get_table_ticket(table_id, collaborator):
    table = DiningTable.query.filter_by(id=table_id, active=True).first_or_404()
    ticket = _current_open_order_for_table(table.id)
    return {
        "table": table.to_dict(),
        "ticket": _ticket_payload(ticket, collaborator) if ticket else None,
        "selected_user": collaborator.to_public_dict(include_pin=True) if collaborator else None,
    }


def _validate_quantity(quantity):
    try:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return None, {"quantity": "Quantidade invalida. Informe um inteiro maior que zero."}
    return quantity, None


def _validate_discount_amount(discount_amount):
    try:
        amount = Decimal(str(discount_amount or "0")).quantize(Decimal("0.01"))
        if amount < 0:
            raise ValueError
    except (ArithmeticError, ValueError):
        return None, {"discount_amount": "Desconto invalido. Informe um valor numerico positivo."}
    return amount, None


def _open_ticket_for_table(table_id):
    table = DiningTable.query.filter_by(id=table_id, active=True).first()
    if table is None:
        return None, None, {"table": "Mesa invalida ou inativa."}

    ticket = _current_open_order_for_table(table.id)
    if ticket is None:
        return table, None, {"ticket": "Nenhum ticket aberto encontrado para esta mesa."}
    return table, ticket, None


def add_product_to_table_ticket(collaborator, table_id, product_id, quantity=1):
    table = DiningTable.query.filter_by(id=table_id, active=True).first()
    if table is None:
        return None, {"table": "Mesa invalida ou inativa."}

    product = MenuProduct.query.filter_by(id=product_id, active=True).first()
    if product is None:
        return None, {"product": "Produto invalido ou inativo."}
    if product.stock_status == "out_of_stock":
        return None, {"product": "Produto sem estoque disponivel no momento."}

    quantity, quantity_error = _validate_quantity(quantity)
    if quantity_error:
        return None, quantity_error

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
    elif not can_manage_ticket(collaborator, ticket):
        return None, {"permission": "Apenas o administrador, a chefia de sala ou o colaborador que abriu esta mesa podem alterá-la."}

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
    return _ticket_payload(ticket, collaborator), None


def update_ticket_item_quantity(collaborator, table_id, item_id, quantity):
    _, ticket, errors = _open_ticket_for_table(table_id)
    if errors:
        return None, errors
    if not can_manage_ticket(collaborator, ticket):
        return None, {"permission": "Voce nao tem permissao para alterar esta mesa."}

    quantity, quantity_error = _validate_quantity(quantity)
    if quantity_error:
        return None, quantity_error

    item = next((entry for entry in ticket.items if entry.id == item_id), None)
    if item is None:
        return None, {"item": "Item nao encontrado neste ticket."}

    item.quantity = quantity
    item.line_total = (Decimal(item.unit_price) * quantity).quantize(Decimal("0.01"))
    db.session.flush()
    ticket.recalculate_total()
    db.session.commit()
    return _ticket_payload(ticket, collaborator), None


def remove_ticket_item(collaborator, table_id, item_id):
    _, ticket, errors = _open_ticket_for_table(table_id)
    if errors:
        return None, errors
    if not can_manage_ticket(collaborator, ticket):
        return None, {"permission": "Voce nao tem permissao para alterar esta mesa."}

    item = next((entry for entry in ticket.items if entry.id == item_id), None)
    if item is None:
        return None, {"item": "Item nao encontrado neste ticket."}

    db.session.delete(item)
    db.session.flush()
    ticket.recalculate_total()
    db.session.commit()
    return _ticket_payload(ticket, collaborator), None


def apply_discount_to_ticket(collaborator, table_id, discount_amount):
    _, ticket, errors = _open_ticket_for_table(table_id)
    if errors:
        return None, errors
    if not can_manage_ticket(collaborator, ticket):
        return None, {"permission": "Voce nao tem permissao para alterar esta mesa."}

    discount_amount, amount_error = _validate_discount_amount(discount_amount)
    if amount_error:
        return None, amount_error

    subtotal = sum(Decimal(item.line_total) for item in ticket.items)
    if discount_amount > subtotal:
        return None, {"discount_amount": "O desconto nao pode ser maior do que o subtotal da conta."}

    ticket.discount_amount = discount_amount
    ticket.recalculate_total()
    db.session.commit()
    return _ticket_payload(ticket, collaborator), None


def close_table_ticket(collaborator, table_id, payment_method):
    _, ticket, errors = _open_ticket_for_table(table_id)
    if errors:
        return None, errors
    if not can_manage_ticket(collaborator, ticket):
        return None, {"permission": "Voce nao tem permissao para fechar esta conta."}

    payment_method = (payment_method or "balcao").strip().lower()
    if payment_method not in {"dinheiro", "cartao", "pix", "balcao"}:
        return None, {"payment_method": "Metodo de pagamento invalido."}
    if not ticket.items:
        return None, {"ticket": "Nao e possivel fechar uma conta sem itens."}

    ticket.recalculate_total()
    ticket.status = "pago"
    ticket.closed_at = utcnow()

    if ticket.payment is None:
        db.session.add(
            Payment(
                order=ticket,
                processed_by=collaborator,
                method=payment_method,
                amount=ticket.total,
            )
        )
    else:
        ticket.payment.method = payment_method
        ticket.payment.amount = ticket.total
        ticket.payment.processed_by = collaborator

    db.session.commit()
    return ticket.to_dict(), None