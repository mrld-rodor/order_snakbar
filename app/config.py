import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    APP_NAME = os.getenv("APP_NAME", "order_snakbar")
    SECRET_KEY = os.getenv(
        "SECRET_KEY", "dev-secret-key-change-me-with-32-chars"
    )
    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY", "dev-jwt-secret-key-change-me-with-32-chars"
    )
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_HOURS", "8"))
    )
    JSON_SORT_KEYS = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///order_snakbar.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(4 * 1024 * 1024)))
    PRODUCT_IMAGE_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    DEMO_SEED_ENABLED = os.getenv("DEMO_SEED_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    DEFAULT_ADMIN_NAME = os.getenv("ADMIN_NAME", "Administrador")
    DEFAULT_ADMIN_CONTACT = os.getenv("ADMIN_CONTACT", "") or os.getenv("ADMIN_EMAIL", "935000001")
    DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
    DEFAULT_COLLABORATOR_NAME = os.getenv("COLLABORATOR_NAME", "Colaborador")
    DEFAULT_COLLABORATOR_CONTACT = os.getenv(
        "COLLABORATOR_CONTACT", ""
    ) or os.getenv("COLLABORATOR_EMAIL", "935000002")
    DEFAULT_COLLABORATOR_PASSWORD = os.getenv(
        "COLLABORATOR_PASSWORD", "colaborador123"
    )
    DEFAULT_FLOOR_CHIEF_NAME = os.getenv("FLOOR_CHIEF_NAME", "Chefe de Sala")
    DEFAULT_FLOOR_CHIEF_CONTACT = os.getenv("FLOOR_CHIEF_CONTACT", "") or os.getenv("FLOOR_CHIEF_EMAIL", "935000003")
    DEFAULT_FLOOR_CHIEF_PASSWORD = os.getenv("FLOOR_CHIEF_PASSWORD", "chefia123")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


def get_config():
    environment = os.getenv("FLASK_ENV", "development").lower()
    if environment == "production":
        return ProductionConfig
    return DevelopmentConfig