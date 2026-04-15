from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.collaborator_management import ensure_collaborator_access
from app.db import db
from app.models import (
    Collaborator,
    DiningTable,
    MenuCategory,
    MenuProduct,
    Order,
    OrderItem,
    Payment,
)

MENU_CATEGORIES = [
    {
        "name": "Cafes",
        "slug": "cafes",
        "description": "Bebidas quentes com foco em extracoes classicas e especiais.",
        "display_order": 1,
    },
    {
        "name": "Sumos Naturais",
        "slug": "sumos-naturais",
        "description": "Bebidas frescas para consumo rapido durante o dia.",
        "display_order": 2,
    },
    {
        "name": "Iced Tea",
        "slug": "iced-tea",
        "description": "Cha gelado artesanal para mesas e takeaway.",
        "display_order": 3,
    },
    {
        "name": "Comidas",
        "slug": "comidas",
        "description": "Lanches e refeicoes leves para rotacao da lanchonete.",
        "display_order": 4,
    },
    {
        "name": "Sobremesas",
        "slug": "sobremesas",
        "description": "Doces de apoio ao ticket medio da operacao.",
        "display_order": 5,
    },
]

MENU_PRODUCTS = [
    {
        "category_slug": "cafes",
        "name": "Espresso Classico",
        "slug": "espresso-classico",
        "description": "Cafe curto com torra media e finalizacao intensa.",
        "price": Decimal("1.80"),
        "stock_quantity": 120,
        "low_stock_threshold": 25,
        "is_vegan": False,
    },
    {
        "category_slug": "cafes",
        "name": "Cappuccino Cremoso",
        "slug": "cappuccino-cremoso",
        "description": "Mistura de espresso, leite vaporizado e canela.",
        "price": Decimal("3.20"),
        "stock_quantity": 54,
        "low_stock_threshold": 12,
        "is_vegan": False,
    },
    {
        "category_slug": "cafes",
        "name": "Latte Baunilha",
        "slug": "latte-baunilha",
        "description": "Cafe suave com leite texturizado e notas de baunilha.",
        "price": Decimal("3.80"),
        "stock_quantity": 40,
        "low_stock_threshold": 10,
        "is_vegan": False,
    },
    {
        "category_slug": "cafes",
        "name": "Mocha Gelado",
        "slug": "mocha-gelado",
        "description": "Bebida fria de chocolate e espresso para dias de maior fluxo.",
        "price": Decimal("4.40"),
        "stock_quantity": 18,
        "low_stock_threshold": 8,
        "is_vegan": False,
    },
    {
        "category_slug": "sumos-naturais",
        "name": "Sumo de Laranja",
        "slug": "sumo-laranja",
        "description": "Laranja espremida na hora, servida sem adicao de acucar.",
        "price": Decimal("3.10"),
        "stock_quantity": 22,
        "low_stock_threshold": 8,
        "is_vegan": False,
    },
    {
        "category_slug": "sumos-naturais",
        "name": "Sumo Verde Detox",
        "slug": "sumo-verde-detox",
        "description": "Abacaxi, couve, maca verde e hortela.",
        "price": Decimal("3.90"),
        "stock_quantity": 14,
        "low_stock_threshold": 6,
        "is_vegan": True,
    },
    {
        "category_slug": "iced-tea",
        "name": "Iced Tea de Limao",
        "slug": "iced-tea-limao",
        "description": "Cha preto artesanal com limao siciliano e gelo.",
        "price": Decimal("2.90"),
        "stock_quantity": 26,
        "low_stock_threshold": 10,
        "is_vegan": True,
    },
    {
        "category_slug": "iced-tea",
        "name": "Iced Tea de Pessego",
        "slug": "iced-tea-pessego",
        "description": "Cha gelado com pessego e toque citrico.",
        "price": Decimal("3.20"),
        "stock_quantity": 6,
        "low_stock_threshold": 6,
        "is_vegan": False,
    },
    {
        "category_slug": "comidas",
        "name": "Croissant Misto",
        "slug": "croissant-misto",
        "description": "Croissant prensado com queijo e fiambre.",
        "price": Decimal("4.80"),
        "stock_quantity": 15,
        "low_stock_threshold": 5,
        "is_vegan": False,
    },
    {
        "category_slug": "comidas",
        "name": "Tosta de Frango",
        "slug": "tosta-frango",
        "description": "Tosta rustica com frango desfiado e creme leve.",
        "price": Decimal("5.60"),
        "stock_quantity": 11,
        "low_stock_threshold": 5,
        "is_vegan": False,
    },
    {
        "category_slug": "comidas",
        "name": "Wrap de Falafel",
        "slug": "wrap-falafel",
        "description": "Wrap vegan com falafel, hummus e salada fresca.",
        "price": Decimal("6.20"),
        "stock_quantity": 9,
        "low_stock_threshold": 4,
        "is_vegan": True,
    },
    {
        "category_slug": "comidas",
        "name": "Bowl de Grao e Abacate",
        "slug": "bowl-grao-abacate",
        "description": "Bowl vegan rico em proteina vegetal e fibras.",
        "price": Decimal("7.10"),
        "stock_quantity": 4,
        "low_stock_threshold": 4,
        "is_vegan": True,
    },
    {
        "category_slug": "sobremesas",
        "name": "Cheesecake de Frutos Vermelhos",
        "slug": "cheesecake-frutos-vermelhos",
        "description": "Sobremesa de vitrine com boa margem e saida constante.",
        "price": Decimal("4.60"),
        "stock_quantity": 7,
        "low_stock_threshold": 6,
        "is_vegan": False,
    },
]

DEMO_COLLABORATORS = [
    {
        "name": "Rita Fonseca",
        "email": "rita.fonseca@cafeteria.local",
        "password": "chefia123",
        "role": "chefe_sala",
    },
    {
        "name": "Ana Costa",
        "email": "ana.costa@cafeteria.local",
        "password": "colaborador123",
        "role": "colaborador",
    },
    {
        "name": "Bruno Lima",
        "email": "bruno.lima@cafeteria.local",
        "password": "colaborador123",
        "role": "colaborador",
    },
    {
        "name": "Carla Dias",
        "email": "carla.dias@cafeteria.local",
        "password": "colaborador123",
        "role": "colaborador",
    },
]


def seed_database(config):
    _ensure_collaborators(config)
    _ensure_categories()
    _ensure_products()
    _ensure_tables()
    db.session.commit()

    if Order.query.count() == 0:
        _seed_orders()
        db.session.commit()


def _ensure_collaborators(config):
    seed_users = [
        {
            "name": config["DEFAULT_ADMIN_NAME"],
            "email": config["DEFAULT_ADMIN_EMAIL"],
            "password": config["DEFAULT_ADMIN_PASSWORD"],
            "role": "administrador",
        },
        {
            "name": config["DEFAULT_COLLABORATOR_NAME"],
            "email": config["DEFAULT_COLLABORATOR_EMAIL"],
            "password": config["DEFAULT_COLLABORATOR_PASSWORD"],
            "role": "colaborador",
        },
        {
            "name": config["DEFAULT_FLOOR_CHIEF_NAME"],
            "email": config["DEFAULT_FLOOR_CHIEF_EMAIL"],
            "password": config["DEFAULT_FLOOR_CHIEF_PASSWORD"],
            "role": "chefe_sala",
        },
        *DEMO_COLLABORATORS,
    ]

    for item in seed_users:
        collaborator = Collaborator.query.filter_by(email=item["email"].lower()).first()
        if collaborator is None:
            collaborator = Collaborator(
                name=item["name"],
                email=item["email"].lower(),
                role=item["role"],
                active=True,
            )
            collaborator.set_password(item["password"])
            db.session.add(collaborator)
        elif collaborator.role != item["role"] and collaborator.email == item["email"].lower():
            collaborator.role = item["role"]

        ensure_collaborator_access(collaborator)


def _ensure_categories():
    for item in MENU_CATEGORIES:
        category = MenuCategory.query.filter_by(slug=item["slug"]).first()
        if category is None:
            db.session.add(MenuCategory(**item))


def _ensure_products():
    categories = {category.slug: category for category in MenuCategory.query.all()}
    for item in MENU_PRODUCTS:
        product = MenuProduct.query.filter_by(slug=item["slug"]).first()
        if product is None:
            payload = dict(item)
            category = categories[payload.pop("category_slug")]
            db.session.add(MenuProduct(category=category, **payload))
        else:
            product.category = categories[item["category_slug"]]
            product.name = item["name"]
            product.description = item["description"]
            product.price = item["price"]
            product.stock_quantity = item["stock_quantity"]
            product.low_stock_threshold = item["low_stock_threshold"]
            product.is_vegan = item["is_vegan"]


def _ensure_tables():
    for number in range(1, 13):
        table = DiningTable.query.filter_by(number=number).first()
        if table is None:
            db.session.add(DiningTable(number=number, seats=4 if number < 9 else 2, active=True))


def _seed_orders():
    now = datetime.now(timezone.utc)
    collaborators = {item.email: item for item in Collaborator.query.all() if item.role == "colaborador"}
    products = {item.slug: item for item in MenuProduct.query.all()}
    tables = {item.number: item for item in DiningTable.query.all()}

    dataset = [
        {
            "table": 1,
            "collaborator": "colaborador@cafeteria.local",
            "paid_at": now - timedelta(hours=1, minutes=15),
            "items": [("espresso-classico", 2), ("croissant-misto", 1)],
            "method": "cartao",
        },
        {
            "table": 2,
            "collaborator": "ana.costa@cafeteria.local",
            "paid_at": now - timedelta(hours=2, minutes=40),
            "items": [("latte-baunilha", 1), ("wrap-falafel", 1), ("iced-tea-limao", 1)],
            "method": "pix",
        },
        {
            "table": 3,
            "collaborator": "bruno.lima@cafeteria.local",
            "paid_at": now - timedelta(hours=4, minutes=5),
            "items": [("mocha-gelado", 2), ("cheesecake-frutos-vermelhos", 2)],
            "method": "dinheiro",
        },
        {
            "table": 4,
            "collaborator": "carla.dias@cafeteria.local",
            "paid_at": now - timedelta(days=2, hours=1),
            "items": [("sumo-verde-detox", 1), ("bowl-grao-abacate", 1)],
            "method": "pix",
        },
        {
            "table": 5,
            "collaborator": "colaborador@cafeteria.local",
            "paid_at": now - timedelta(days=3, hours=3),
            "items": [("cappuccino-cremoso", 2), ("tosta-frango", 1)],
            "method": "cartao",
        },
        {
            "table": 6,
            "collaborator": "ana.costa@cafeteria.local",
            "paid_at": now - timedelta(days=6, hours=2),
            "items": [("sumo-laranja", 2), ("croissant-misto", 2)],
            "method": "cartao",
        },
        {
            "table": 7,
            "collaborator": "bruno.lima@cafeteria.local",
            "paid_at": now - timedelta(days=10, hours=5),
            "items": [("iced-tea-pessego", 2), ("cheesecake-frutos-vermelhos", 1)],
            "method": "pix",
        },
        {
            "table": 8,
            "collaborator": "carla.dias@cafeteria.local",
            "paid_at": now - timedelta(days=15, hours=4),
            "items": [("espresso-classico", 1), ("tosta-frango", 1), ("cheesecake-frutos-vermelhos", 1)],
            "method": "dinheiro",
        },
        {
            "table": 9,
            "collaborator": "colaborador@cafeteria.local",
            "paid_at": now - timedelta(days=23, hours=2),
            "items": [("wrap-falafel", 2), ("sumo-verde-detox", 1)],
            "method": "pix",
        },
    ]

    for item in dataset:
        collaborator = collaborators[item["collaborator"]]
        order = Order(
            table=tables[item["table"]],
            collaborator=collaborator,
            status="pago",
            notes="Pedido seed para demonstracao analitica.",
            opened_at=item["paid_at"] - timedelta(minutes=18),
            closed_at=item["paid_at"],
        )
        db.session.add(order)

        for product_slug, quantity in item["items"]:
            product = products[product_slug]
            unit_price = Decimal(product.price)
            line_total = (unit_price * quantity).quantize(Decimal("0.01"))
            db.session.add(
                OrderItem(
                    order=order,
                    product=product,
                    product_name_snapshot=product.name,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )

        order.recalculate_total()
        db.session.add(
            Payment(
                order=order,
                processed_by=collaborator,
                method=item["method"],
                amount=order.total,
                paid_at=item["paid_at"],
            )
        )

    open_order = Order(
        table=tables[10],
        collaborator=collaborators["ana.costa@cafeteria.local"],
        status="aberto",
        notes="Pedido ainda em atendimento.",
        opened_at=now - timedelta(minutes=12),
    )
    db.session.add(open_order)
    snack = products["croissant-misto"]
    db.session.add(
        OrderItem(
            order=open_order,
            product=snack,
            product_name_snapshot=snack.name,
            quantity=1,
            unit_price=Decimal(snack.price),
            line_total=Decimal(snack.price),
        )
    )
    open_order.recalculate_total()