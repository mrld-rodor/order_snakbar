from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import inspect as sqlalchemy_inspect
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import db


def utcnow():
    return datetime.now(timezone.utc)


class Collaborator(db.Model):
    __tablename__ = "collaborators"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    access_code = db.Column(db.String(5), unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    pin_hash = db.Column(db.String(255))
    pin_code = db.Column(db.String(4))
    role = db.Column(db.String(30), nullable=False, default="colaborador")
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    orders = db.relationship("Order", back_populates="collaborator", lazy=True)
    payments = db.relationship("Payment", back_populates="processed_by", lazy=True)

    @property
    def contact(self):
        return self.email

    @contact.setter
    def contact(self, value):
        self.email = value

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_pin(self, pin):
        normalized_pin = str(pin).zfill(4)
        self.pin_hash = generate_password_hash(normalized_pin)
        self.pin_code = normalized_pin

    def check_pin(self, pin):
        if not self.pin_hash:
            return False
        return check_password_hash(self.pin_hash, str(pin))

    def to_public_dict(self, include_pin=False):
        payload = {
            "id": self.id,
            "name": self.name,
            "contact": self.contact,
            "email": self.contact,
            "access_code": self.access_code,
            "role": self.role,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_pin:
            payload["pin_code"] = self.pin_code
        return payload


class MenuCategory(db.Model):
    __tablename__ = "menu_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    slug = db.Column(db.String(80), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255))
    display_order = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)

    products = db.relationship("MenuProduct", back_populates="category", lazy=True)

    def to_dict(self, include_products=False):
        payload = {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "display_order": self.display_order,
            "active": self.active,
            "product_count": len([product for product in self.products if product.active]),
        }
        if include_products:
            active_products = [product for product in self.products if product.active]
            payload["products"] = [product.to_dict() for product in active_products]
        return payload


class MenuProduct(db.Model):
    __tablename__ = "menu_products"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("menu_categories.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    low_stock_threshold = db.Column(db.Integer, nullable=False, default=5)
    is_vegan = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    image_filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    category = db.relationship("MenuCategory", back_populates="products")
    order_items = db.relationship("OrderItem", back_populates="product", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "category_id": self.category_id,
            "category_slug": self.category.slug if self.category else None,
            "category": self.category.name if self.category else None,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "price": float(self.price),
            "stock_quantity": self.stock_quantity,
            "low_stock_threshold": self.low_stock_threshold,
            "stock_status": self.stock_status,
            "is_vegan": self.is_vegan,
            "active": self.active,
            "image_filename": self.image_filename,
            "image_url": f"/static/uploads/products/{self.image_filename}" if self.image_filename else None,
        }

    @property
    def stock_status(self):
        if self.stock_quantity <= 0:
            return "out_of_stock"
        if self.stock_quantity <= self.low_stock_threshold:
            return "low_stock"
        return "healthy"


class DiningTable(db.Model):
    __tablename__ = "dining_tables"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False, unique=True, index=True)
    seats = db.Column(db.Integer, nullable=False, default=4)
    active = db.Column(db.Boolean, nullable=False, default=True)

    orders = db.relationship("Order", back_populates="table", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "number": self.number,
            "seats": self.seats,
            "active": self.active,
        }


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey("dining_tables.id"), nullable=False)
    collaborator_id = db.Column(db.Integer, db.ForeignKey("collaborators.id"), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="aberto")
    notes = db.Column(db.String(255))
    sale_pin_code = db.Column(db.String(4))
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    total = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    opened_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    closed_at = db.Column(db.DateTime(timezone=True))

    table = db.relationship("DiningTable", back_populates="orders")
    collaborator = db.relationship("Collaborator", back_populates="orders")
    items = db.relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan", lazy=True
    )
    payment = db.relationship(
        "Payment", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )

    def recalculate_total(self):
        subtotal = Decimal("0.00")
        for item in self.items:
            if sqlalchemy_inspect(item).deleted:
                continue
            subtotal += Decimal(item.line_total)

        discount_amount = Decimal(self.discount_amount or 0)
        if discount_amount < 0:
            discount_amount = Decimal("0.00")
        if discount_amount > subtotal:
            discount_amount = subtotal

        self.subtotal = subtotal.quantize(Decimal("0.01"))
        self.discount_amount = discount_amount.quantize(Decimal("0.01"))
        self.total = (subtotal - discount_amount).quantize(Decimal("0.01"))

    def to_dict(self):
        owner_payload = self.collaborator.to_public_dict() if self.collaborator else None
        return {
            "id": self.id,
            "table_id": self.table_id,
            "table_number": self.table.number if self.table else None,
            "collaborator_id": self.collaborator_id,
            "collaborator": self.collaborator.name if self.collaborator else None,
            "owner": owner_payload,
            "sale_credentials": {
                "username": self.collaborator.access_code if self.collaborator and self.collaborator.access_code else (self.collaborator.contact if self.collaborator else None),
                "password": self.sale_pin_code,
            },
            "status": self.status,
            "notes": self.notes,
            "subtotal": float(self.subtotal),
            "discount_amount": float(self.discount_amount),
            "total": float(self.total),
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "items": [item.to_dict() for item in self.items],
            "payment": self.payment.to_dict() if self.payment else None,
        }


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("menu_products.id"), nullable=False)
    product_name_snapshot = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("MenuProduct", back_populates="order_items")

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "name": self.product_name_snapshot,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "line_total": float(self.line_total),
            "is_vegan": self.product.is_vegan if self.product else False,
        }


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, unique=True)
    collaborator_id = db.Column(db.Integer, db.ForeignKey("collaborators.id"), nullable=False)
    method = db.Column(db.String(30), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    paid_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    order = db.relationship("Order", back_populates="payment")
    processed_by = db.relationship("Collaborator", back_populates="payments")

    def to_dict(self):
        return {
            "id": self.id,
            "method": self.method,
            "amount": float(self.amount),
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
        }