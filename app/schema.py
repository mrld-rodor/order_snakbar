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