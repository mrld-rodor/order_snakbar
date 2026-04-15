import os
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.db import db
from app.models import MenuCategory, MenuProduct


def slugify(value):
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return cleaned or f"produto-{uuid4().hex[:8]}"


def allowed_image(filename):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return extension in current_app.config["PRODUCT_IMAGE_ALLOWED_EXTENSIONS"]


def parse_product_payload(form_data):
    name = (form_data.get("name") or "").strip()
    description = (form_data.get("description") or "").strip()
    category_id = form_data.get("category_id")
    price_raw = (form_data.get("price") or "").strip().replace(",", ".")

    errors = {}
    if not name:
        errors["name"] = "Nome do produto e obrigatorio."
    if not description:
        errors["description"] = "Descricao do produto e obrigatoria."

    category = None
    if not category_id:
        errors["category_id"] = "Categoria e obrigatoria."
    else:
        category = MenuCategory.query.get(category_id)
        if category is None or not category.active:
            errors["category_id"] = "Categoria invalida ou inativa."

    price = None
    try:
        price = Decimal(price_raw).quantize(Decimal("0.01"))
        if price <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errors["price"] = "Preco invalido. Informe um valor maior que zero."

    stock_quantity = None
    low_stock_threshold = None
    try:
        stock_quantity = int((form_data.get("stock_quantity") or "0").strip())
        if stock_quantity < 0:
            raise ValueError
    except ValueError:
        errors["stock_quantity"] = "Estoque invalido. Informe um numero inteiro maior ou igual a zero."

    try:
        low_stock_threshold = int((form_data.get("low_stock_threshold") or "0").strip())
        if low_stock_threshold < 0:
            raise ValueError
    except ValueError:
        errors["low_stock_threshold"] = (
            "Limite minimo invalido. Informe um numero inteiro maior ou igual a zero."
        )

    active = str(form_data.get("active", "true")).lower() in {"true", "1", "on", "yes"}
    is_vegan = str(form_data.get("is_vegan", "false")).lower() in {
        "true",
        "1",
        "on",
        "yes",
    }

    return {
        "errors": errors,
        "name": name,
        "description": description,
        "category": category,
        "price": price,
        "stock_quantity": stock_quantity,
        "low_stock_threshold": low_stock_threshold,
        "active": active,
        "is_vegan": is_vegan,
    }


def _build_unique_slug(name, current_product=None):
    base_slug = slugify(name)
    slug = base_slug
    index = 2

    while True:
        existing = MenuProduct.query.filter_by(slug=slug).first()
        if existing is None or (current_product and existing.id == current_product.id):
            return slug
        slug = f"{base_slug}-{index}"
        index += 1


def save_product_image(file_storage):
    if not file_storage or not isinstance(file_storage, FileStorage):
        return None
    if file_storage.filename == "":
        return None
    if not allowed_image(file_storage.filename):
        raise ValueError("Formato de imagem invalido. Use PNG, JPG, JPEG, GIF ou WEBP.")

    filename = secure_filename(file_storage.filename)
    extension = filename.rsplit(".", 1)[-1].lower()
    unique_filename = f"{uuid4().hex}.{extension}"
    upload_folder = current_app.config["PRODUCT_IMAGE_UPLOAD_DIR"]
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, unique_filename))
    return unique_filename


def delete_product_image(filename):
    if not filename:
        return
    upload_folder = current_app.config["PRODUCT_IMAGE_UPLOAD_DIR"]
    target_path = os.path.join(upload_folder, filename)
    if os.path.exists(target_path):
        os.remove(target_path)


def create_product(form_data, image_file=None):
    payload = parse_product_payload(form_data)
    if payload["errors"]:
        return None, payload["errors"]

    image_filename = None
    if image_file and image_file.filename:
        try:
            image_filename = save_product_image(image_file)
        except ValueError as error:
            return None, {"image": str(error)}

    product = MenuProduct(
        category=payload["category"],
        name=payload["name"],
        slug=_build_unique_slug(payload["name"]),
        description=payload["description"],
        price=payload["price"],
        stock_quantity=payload["stock_quantity"],
        low_stock_threshold=payload["low_stock_threshold"],
        is_vegan=payload["is_vegan"],
        active=payload["active"],
        image_filename=image_filename,
    )
    db.session.add(product)
    db.session.commit()
    return product, None


def update_product(product, form_data, image_file=None):
    payload = parse_product_payload(form_data)
    if payload["errors"]:
        return None, payload["errors"]

    remove_image = str(form_data.get("remove_image", "false")).lower() in {
        "true",
        "1",
        "on",
        "yes",
    }

    if image_file and image_file.filename:
        try:
            new_filename = save_product_image(image_file)
        except ValueError as error:
            return None, {"image": str(error)}
        delete_product_image(product.image_filename)
        product.image_filename = new_filename
    elif remove_image:
        delete_product_image(product.image_filename)
        product.image_filename = None

    product.category = payload["category"]
    product.name = payload["name"]
    product.slug = _build_unique_slug(payload["name"], current_product=product)
    product.description = payload["description"]
    product.price = payload["price"]
    product.stock_quantity = payload["stock_quantity"]
    product.low_stock_threshold = payload["low_stock_threshold"]
    product.is_vegan = payload["is_vegan"]
    product.active = payload["active"]

    db.session.commit()
    return product, None


def delete_product(product):
    if product.order_items:
        product.active = False
        db.session.commit()
        return "deactivated"

    delete_product_image(product.image_filename)
    db.session.delete(product)
    db.session.commit()
    return "deleted"


def list_products(include_inactive=False):
    query = MenuProduct.query.order_by(MenuProduct.name.asc())
    if not include_inactive:
        query = query.filter_by(active=True)
    return [product.to_dict() for product in query.all()]