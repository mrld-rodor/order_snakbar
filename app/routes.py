from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import create_access_token, jwt_required

from app.analytics import (
    get_admin_dashboard,
    get_collaborator_admin_dashboard,
    get_collaborators_list,
    get_catalog_overview,
    get_collaborator_dashboard,
    get_collaborator_rankings,
    get_menu_catalog,
    get_product_dashboard,
    get_recent_orders,
    get_sales_summary,
)
from app.auth import (
    authenticate_user,
    get_current_collaborator,
    public_user_data,
    role_required,
)
from app.collaborator_ordering import (
    add_product_to_table_ticket,
    get_collaborator_ordering_bootstrap,
    get_table_ticket,
)
from app.models import Collaborator
from app.models import MenuCategory, MenuProduct
from app.product_admin import create_product, delete_product, list_products, update_product

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
        "collaborator_panel.html",
        app_name=current_app.config["APP_NAME"],
        page_title="Painel do Colaborador",
    )


@main_blueprint.get("/admin")
def admin_page():
    return redirect(url_for("main.admin_products_dashboard_page"))


@main_blueprint.get("/admin/produtos")
def admin_products_dashboard_page():
    return render_template(
        "admin_sales.html",
        app_name=current_app.config["APP_NAME"],
        page_title="Painel de Produtos e Vendas",
    )


@main_blueprint.get("/admin/colaboradores")
def admin_collaborators_page():
    return render_template(
        "admin_collaborators.html",
        app_name=current_app.config["APP_NAME"],
        page_title="Painel de Colaboradores",
    )


@main_blueprint.get("/admin/catalogo")
def admin_catalog_page():
    return render_template(
        "admin_products.html",
        app_name=current_app.config["APP_NAME"],
        expected_role="administrador",
        page_title="Painel de Catalogo",
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


@main_blueprint.get("/api/colaborador/ordering/bootstrap")
@role_required("colaborador", "administrador")
def collaborator_ordering_bootstrap():
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404
    return jsonify(get_collaborator_ordering_bootstrap(collaborator))


@main_blueprint.get("/api/colaborador/tables/<int:table_id>/ticket")
@role_required("colaborador", "administrador")
def collaborator_table_ticket(table_id):
    return jsonify(get_table_ticket(table_id))


@main_blueprint.post("/api/colaborador/tables/<int:table_id>/ticket/items")
@role_required("colaborador", "administrador")
def collaborator_add_ticket_item(table_id):
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404

    payload = request.get_json(silent=True) or {}
    ticket, errors = add_product_to_table_ticket(
        collaborator,
        table_id=table_id,
        product_id=payload.get("product_id"),
        quantity=payload.get("quantity", 1),
    )
    if errors:
        return jsonify({"message": "Falha ao adicionar item ao ticket.", "errors": errors}), 400
    return jsonify({"message": "Item adicionado ao ticket com sucesso.", "ticket": ticket}), 201


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


@main_blueprint.get("/api/admin/products/dashboard")
@role_required("administrador")
def admin_products_dashboard():
    period = request.args.get("period", "day")
    return jsonify(get_product_dashboard(period))


@main_blueprint.get("/api/admin/categories")
@role_required("administrador")
def admin_categories():
    categories = MenuCategory.query.order_by(MenuCategory.display_order.asc()).all()
    return jsonify({"categories": [category.to_dict() for category in categories]})


@main_blueprint.get("/api/admin/products")
@role_required("administrador")
def admin_products():
    include_inactive = request.args.get("include_inactive", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return jsonify({"products": list_products(include_inactive=include_inactive)})


@main_blueprint.post("/api/admin/products")
@role_required("administrador")
def admin_product_create():
    product, errors = create_product(request.form, request.files.get("image"))
    if errors:
        return jsonify({"message": "Falha ao criar produto.", "errors": errors}), 400
    return jsonify({"message": "Produto criado com sucesso.", "product": product.to_dict()}), 201


@main_blueprint.put("/api/admin/products/<int:product_id>")
@role_required("administrador")
def admin_product_update(product_id):
    product = MenuProduct.query.get_or_404(product_id)
    updated_product, errors = update_product(product, request.form, request.files.get("image"))
    if errors:
        return jsonify({"message": "Falha ao atualizar produto.", "errors": errors}), 400
    return jsonify(
        {"message": "Produto atualizado com sucesso.", "product": updated_product.to_dict()}
    )


@main_blueprint.delete("/api/admin/products/<int:product_id>")
@role_required("administrador")
def admin_product_delete(product_id):
    product = MenuProduct.query.get_or_404(product_id)
    action = delete_product(product)
    if action == "deactivated":
        return jsonify(
            {
                "message": "Produto desativado porque possui historico de vendas.",
                "action": action,
            }
        )
    return jsonify({"message": "Produto removido com sucesso.", "action": action})


@main_blueprint.get("/api/admin/analytics/summary")
@role_required("administrador")
def admin_analytics_summary():
    period = request.args.get("period", "day")
    return jsonify(get_sales_summary(period))


@main_blueprint.get("/api/admin/collaborators")
@role_required("administrador")
def admin_collaborators_list():
    return jsonify({"collaborators": get_collaborators_list()})


@main_blueprint.get("/api/admin/collaborators/dashboard")
@role_required("administrador")
def admin_collaborators_dashboard():
    period = request.args.get("period", "day")
    collaborator_id = request.args.get("collaborator_id", type=int)
    return jsonify(get_collaborator_admin_dashboard(period, collaborator_id))


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