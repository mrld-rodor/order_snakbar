import os

from flask import Flask
from flask_jwt_extended import JWTManager

from app.config import get_config
from app.db import db
from app.routes import main_blueprint
from app.schema import ensure_database_schema
from app.seed import seed_database


def create_app(config_class=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    app.config.from_object(config_class or get_config())
    app.config.setdefault(
        "PRODUCT_IMAGE_UPLOAD_DIR",
        os.path.join(app.static_folder, "uploads", "products"),
    )
    JWTManager(app)
    db.init_app(app)
    app.register_blueprint(main_blueprint)

    with app.app_context():
        db.create_all()
        ensure_database_schema()
        os.makedirs(app.config["PRODUCT_IMAGE_UPLOAD_DIR"], exist_ok=True)
        if app.config["DEMO_SEED_ENABLED"]:
            seed_database(app.config)

    return app