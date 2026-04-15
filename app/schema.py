from sqlalchemy import inspect, text

from app.db import db


def ensure_database_schema():
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())

    if "menu_products" in tables:
        columns = {column["name"] for column in inspector.get_columns("menu_products")}
        if "image_filename" not in columns:
            db.session.execute(
                text("ALTER TABLE menu_products ADD COLUMN image_filename VARCHAR(255)")
            )
            db.session.commit()
        if "stock_quantity" not in columns:
            db.session.execute(
                text("ALTER TABLE menu_products ADD COLUMN stock_quantity INTEGER DEFAULT 0 NOT NULL")
            )
            db.session.commit()
        if "low_stock_threshold" not in columns:
            db.session.execute(
                text(
                    "ALTER TABLE menu_products ADD COLUMN low_stock_threshold INTEGER DEFAULT 5 NOT NULL"
                )
            )
            db.session.commit()

    if "collaborators" in tables:
        columns = {column["name"] for column in inspector.get_columns("collaborators")}
        if "access_code" not in columns:
            db.session.execute(text("ALTER TABLE collaborators ADD COLUMN access_code VARCHAR(5)"))
            db.session.commit()
        db.session.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_collaborators_access_code ON collaborators (access_code)"
            )
        )
        db.session.commit()
        if "pin_hash" not in columns:
            db.session.execute(text("ALTER TABLE collaborators ADD COLUMN pin_hash VARCHAR(255)"))
            db.session.commit()
        if "pin_code" not in columns:
            db.session.execute(text("ALTER TABLE collaborators ADD COLUMN pin_code VARCHAR(4)"))
            db.session.commit()

    if "orders" in tables:
        columns = {column["name"] for column in inspector.get_columns("orders")}
        if "subtotal" not in columns:
            db.session.execute(
                text("ALTER TABLE orders ADD COLUMN subtotal NUMERIC(10, 2) DEFAULT 0.00 NOT NULL")
            )
            db.session.commit()
        if "discount_amount" not in columns:
            db.session.execute(
                text(
                    "ALTER TABLE orders ADD COLUMN discount_amount NUMERIC(10, 2) DEFAULT 0.00 NOT NULL"
                )
            )
            db.session.commit()
        db.session.execute(
            text(
                "UPDATE orders SET subtotal = total WHERE subtotal IS NULL OR subtotal = 0"
            )
        )
        db.session.execute(
            text(
                "UPDATE orders SET discount_amount = 0 WHERE discount_amount IS NULL"
            )
        )
        db.session.commit()