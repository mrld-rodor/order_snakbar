from flask import Flask
from flask_jwt_extended import JWTManager

from app.config import get_config
from app.db import db
from app.routes import main_blueprint
from app.seed import seed_database


def create_app(config_class=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    app.config.from_object(config_class or get_config())
    JWTManager(app)
    db.init_app(app)
    app.register_blueprint(main_blueprint)

    with app.app_context():
        db.create_all()
        if app.config["DEMO_SEED_ENABLED"]:
            seed_database(app.config)

    return app