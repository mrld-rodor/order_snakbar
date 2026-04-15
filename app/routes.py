from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_jwt_extended import create_access_token, jwt_required

from app.analytics import (
    get_admin_dashboard,
    get_catalog_overview,
    get_collaborator_dashboard,
    get_collaborator_rankings,
    get_menu_catalog,
    get_recent_orders,
    get_sales_summary,
)
from app.auth import (
    authenticate_user,
    get_current_collaborator,
    public_user_data,
    role_required,
)
from app.models import Collaborator

main_blueprint = Blueprint("main", __name__)


@main_blueprint.get("/")
def index():
    return render_template("index.html", app_name=current_app.config["APP_NAME"])


@main_blueprint.get("/login")
def login_page():
    return render_template("login.html", app_name=current_app.config["APP_NAME"])


@main_blueprint.get("/colaborador")
def collaborator_page():
    return render_template(
        "dashboard.html",
        app_name=current_app.config["APP_NAME"],
        expected_role="colaborador",
        page_title="Painel do Colaborador",
        api_endpoint="/api/colaborador/area",
    )


@main_blueprint.get("/admin")
def admin_page():
    return render_template(
        "dashboard.html",
        app_name=current_app.config["APP_NAME"],
        expected_role="administrador",
        page_title="Painel do Administrador",
        api_endpoint="/api/admin/area",
    )


@main_blueprint.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return jsonify({"message": "Email e senha sao obrigatorios."}), 400

    user = authenticate_user(email, password)
    if not user:
        return jsonify({"message": "Credenciais invalidas."}), 401

    token = create_access_token(
        identity=str(user["id"]),
        additional_claims={
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
        },
    )

    return jsonify({"access_token": token, "user": user})


@main_blueprint.get("/api/catalog/menu")
def menu_catalog():
    return jsonify(get_menu_catalog())


@main_blueprint.get("/api/auth/me")
@jwt_required()
def current_user():
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404
    return jsonify({"user": public_user_data(collaborator)})


@main_blueprint.get("/api/colaborador/area")
@role_required("colaborador", "administrador")
def collaborator_area():
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404
    return jsonify(get_collaborator_dashboard(collaborator))


@main_blueprint.get("/api/admin/area")
@role_required("administrador")
def admin_area():
    return jsonify(get_admin_dashboard())


@main_blueprint.get("/api/colaborador/performance")
@role_required("colaborador", "administrador")
def collaborator_performance():
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404
    period = request.args.get("period", "day")
    return jsonify(
        {
            "user": collaborator.to_public_dict(),
            "summary": get_sales_summary(period, collaborator.id),
            "recent_orders": get_recent_orders(limit=5, collaborator_id=collaborator.id),
        }
    )


@main_blueprint.get("/api/admin/catalog/overview")
@role_required("administrador")
def admin_catalog_overview():
    return jsonify(get_catalog_overview())


@main_blueprint.get("/api/admin/analytics/summary")
@role_required("administrador")
def admin_analytics_summary():
    period = request.args.get("period", "day")
    return jsonify(get_sales_summary(period))


@main_blueprint.get("/api/admin/analytics/collaborators")
@role_required("administrador")
def admin_collaborator_analytics():
    period = request.args.get("period", "month")
    return jsonify({"period": period, "ranking": get_collaborator_rankings(period)})


@main_blueprint.get("/api/admin/collaborators/<int:collaborator_id>/performance")
@role_required("administrador")
def admin_collaborator_performance(collaborator_id):
    collaborator = Collaborator.query.get_or_404(collaborator_id)
    period = request.args.get("period", "month")
    return jsonify(
        {
            "user": collaborator.to_public_dict(),
            "summary": get_sales_summary(period, collaborator.id),
            "recent_orders": get_recent_orders(limit=8, collaborator_id=collaborator.id),
        }
    )


@main_blueprint.get("/health")
@main_blueprint.get("/api/health")
def health_check():
    return jsonify(
        {
            "status": "ok",
            "application": current_app.config["APP_NAME"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )