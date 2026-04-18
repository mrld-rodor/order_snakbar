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
from app.collaborator_management import (
    create_collaborator_account,
    delete_collaborator_account,
    list_manageable_collaborators,
    update_collaborator_account,
)
from app.collaborator_ordering import (
    add_product_to_table_ticket,
    apply_discount_to_ticket,
    close_table_ticket,
    get_collaborator_ordering_bootstrap,
    get_public_ordering_bootstrap,
    get_table_ticket,
    remove_ticket_item,
    update_ticket_item_quantity,
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
    return redirect(url_for("main.operations_page"))


@main_blueprint.get("/operacao")
def operations_page():
    return render_template(
        "collaborator_panel.html",
        app_name=current_app.config["APP_NAME"],
        page_title="Tela Central de Vendas",
        page_description="Tela central da operacao: escolha a mesa, valide a credencial do responsavel, continue a venda ou lance novos pedidos em tempo real.",
    )


@main_blueprint.get("/chefia/vendas")
def floor_chief_sales_page():
    return redirect(url_for("main.operations_page"))


@main_blueprint.get("/admin")
def admin_page():
    return redirect(url_for("main.admin_collaborators_management_page"))


@main_blueprint.get("/admin/produtos")
def admin_products_dashboard_page():
    return redirect(url_for("main.admin_catalog_page"))


@main_blueprint.get("/admin/colaboradores")
def admin_collaborators_page():
    return render_template(
        "admin_collaborators.html",
        app_name=current_app.config["APP_NAME"],
        page_title="Produtividade da Equipa",
        show_admin_nav=True,
        show_management=False,
        show_productivity=True,
        productivity_url=url_for("main.admin_collaborators_page"),
        management_url=url_for("main.admin_collaborators_management_page"),
        sales_url=url_for("main.operations_page"),
        active_collaborator_tab="produtividade",
        initial_collaborator_id=request.args.get("collaborator_id", type=int),
        active_admin_tab="produtividade",
    )


@main_blueprint.get("/admin/colaboradores/gerenciamento")
def admin_collaborators_management_page():
    return render_template(
        "admin_collaborators.html",
        app_name=current_app.config["APP_NAME"],
        page_title="Gerenciamento de Colaboradores",
        show_admin_nav=True,
        show_management=True,
        show_productivity=False,
        productivity_url=url_for("main.admin_collaborators_page"),
        management_url=url_for("main.admin_collaborators_management_page"),
        sales_url=url_for("main.operations_page"),
        active_collaborator_tab="gerenciamento",
        initial_collaborator_id=None,
        active_admin_tab="gerenciamento",
    )


@main_blueprint.get("/chefia")
def floor_chief_page():
    return render_template(
        "admin_collaborators.html",
        app_name=current_app.config["APP_NAME"],
        page_title="Produtividade da Chefia",
        show_admin_nav=False,
        show_management=False,
        show_productivity=True,
        productivity_url=url_for("main.floor_chief_page"),
        management_url=url_for("main.floor_chief_management_page"),
        sales_url=url_for("main.floor_chief_sales_page"),
        active_collaborator_tab="produtividade",
        initial_collaborator_id=request.args.get("collaborator_id", type=int),
    )


@main_blueprint.get("/chefia/colaboradores")
def floor_chief_management_page():
    return render_template(
        "admin_collaborators.html",
        app_name=current_app.config["APP_NAME"],
        page_title="Gerenciamento da Chefia",
        show_admin_nav=False,
        show_management=True,
        show_productivity=False,
        productivity_url=url_for("main.floor_chief_page"),
        management_url=url_for("main.floor_chief_management_page"),
        sales_url=url_for("main.floor_chief_sales_page"),
        active_collaborator_tab="gerenciamento",
        initial_collaborator_id=None,
    )


@main_blueprint.get("/chefia/estoque")
def floor_chief_stock_page():
    return render_template(
        "admin_products.html",
        app_name=current_app.config["APP_NAME"],
        page_title="Consulta de Estoque da Chefia",
        page_description="Consulta operacional do catalogo: acompanhe estoque, alertas e disponibilidade dos produtos sem permissoes de edicao.",
        show_admin_nav=False,
        read_only=True,
        overview_endpoint="/api/chefia/estoque/overview",
        categories_endpoint="/api/chefia/categorias",
        products_endpoint="/api/chefia/produtos",
        sales_url=url_for("main.floor_chief_sales_page"),
        productivity_url=url_for("main.floor_chief_page"),
        management_url=url_for("main.floor_chief_management_page"),
        stock_url=url_for("main.floor_chief_stock_page"),
        active_chief_tab="estoque",
    )


@main_blueprint.get("/admin/catalogo")
def admin_catalog_page():
    return render_template(
        "admin_products.html",
        app_name=current_app.config["APP_NAME"],
        expected_role="administrador",
        page_title="Painel de Estoque e Catalogo",
        api_endpoint="/api/admin/area",
        show_admin_nav=True,
        active_admin_tab="estoque",
    )


@main_blueprint.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    identifier = (payload.get("identifier") or payload.get("contact") or payload.get("email") or "").strip()
    secret = payload.get("secret") or payload.get("password") or ""

    if not identifier or not secret:
        return jsonify({"message": "Identificador e senha sao obrigatorios."}), 400

    user = authenticate_user(identifier, secret)
    if not user:
        return jsonify({"message": "Credenciais invalidas."}), 401

    token = create_access_token(
        identity=str(user["id"]),
        additional_claims={
            "contact": user.get("contact"),
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
@role_required("colaborador", "administrador", "chefe_sala")
def collaborator_area():
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404
    return jsonify(get_collaborator_dashboard(collaborator))


@main_blueprint.get("/api/colaborador/ordering/bootstrap")
@role_required("colaborador", "administrador", "chefe_sala")
def collaborator_ordering_bootstrap():
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404
    return jsonify(get_collaborator_ordering_bootstrap(collaborator))


@main_blueprint.get("/api/operacao/bootstrap-public")
def public_ordering_bootstrap():
    return jsonify(get_public_ordering_bootstrap())


@main_blueprint.get("/api/colaborador/tables/<int:table_id>/ticket")
@role_required("colaborador", "administrador", "chefe_sala")
def collaborator_table_ticket(table_id):
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404
    return jsonify(get_table_ticket(table_id, collaborator))


@main_blueprint.post("/api/colaborador/tables/<int:table_id>/ticket/items")
@role_required("colaborador", "administrador", "chefe_sala")
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


@main_blueprint.put("/api/colaborador/tables/<int:table_id>/ticket/items/<int:item_id>")
@role_required("colaborador", "administrador", "chefe_sala")
def collaborator_update_ticket_item(table_id, item_id):
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404

    payload = request.get_json(silent=True) or {}
    ticket, errors = update_ticket_item_quantity(
        collaborator=collaborator,
        table_id=table_id,
        item_id=item_id,
        quantity=payload.get("quantity"),
    )
    if errors:
        return jsonify({"message": "Falha ao atualizar item do ticket.", "errors": errors}), 400
    return jsonify({"message": "Item atualizado com sucesso.", "ticket": ticket})


@main_blueprint.delete("/api/colaborador/tables/<int:table_id>/ticket/items/<int:item_id>")
@role_required("colaborador", "administrador", "chefe_sala")
def collaborator_delete_ticket_item(table_id, item_id):
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404

    ticket, errors = remove_ticket_item(collaborator=collaborator, table_id=table_id, item_id=item_id)
    if errors:
        return jsonify({"message": "Falha ao remover item do ticket.", "errors": errors}), 400
    return jsonify({"message": "Item removido com sucesso.", "ticket": ticket})


@main_blueprint.put("/api/colaborador/tables/<int:table_id>/ticket/discount")
@role_required("colaborador", "administrador", "chefe_sala")
def collaborator_apply_discount(table_id):
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404

    payload = request.get_json(silent=True) or {}
    ticket, errors = apply_discount_to_ticket(
        collaborator=collaborator,
        table_id=table_id,
        discount_amount=payload.get("discount_amount"),
    )
    if errors:
        return jsonify({"message": "Falha ao aplicar desconto.", "errors": errors}), 400
    return jsonify({"message": "Desconto atualizado com sucesso.", "ticket": ticket})


@main_blueprint.put("/api/colaborador/tables/<int:table_id>/ticket/close")
@role_required("colaborador", "administrador", "chefe_sala")
def collaborator_close_ticket(table_id):
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404

    payload = request.get_json(silent=True) or {}
    ticket, errors = close_table_ticket(
        collaborator=collaborator,
        table_id=table_id,
        payment_method=payload.get("payment_method"),
    )
    if errors:
        return jsonify({"message": "Falha ao fechar a conta.", "errors": errors}), 400
    return jsonify({"message": "Conta fechada com sucesso.", "ticket": ticket})


@main_blueprint.get("/api/admin/area")
@role_required("administrador")
def admin_area():
    return jsonify(get_admin_dashboard())


@main_blueprint.get("/api/chefia/estoque/overview")
@role_required("chefe_sala")
def floor_chief_stock_overview():
    dashboard = get_admin_dashboard()
    return jsonify(
        {
            "overview": dashboard.get("overview", {}),
            "catalog": dashboard.get("catalog", {}),
            "inventory": dashboard.get("inventory", {}),
        }
    )


@main_blueprint.get("/api/colaborador/performance")
@role_required("colaborador", "administrador", "chefe_sala")
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


@main_blueprint.get("/api/chefia/categorias")
@role_required("chefe_sala")
def floor_chief_categories():
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


@main_blueprint.get("/api/chefia/produtos")
@role_required("chefe_sala")
def floor_chief_products():
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
@role_required("administrador", "chefe_sala")
def admin_collaborators_list():
    return jsonify({"collaborators": get_collaborators_list()})


@main_blueprint.get("/api/admin/collaborators/dashboard")
@role_required("administrador", "chefe_sala")
def admin_collaborators_dashboard():
    period = request.args.get("period", "day")
    collaborator_id = request.args.get("collaborator_id", type=int)
    return jsonify(get_collaborator_admin_dashboard(period, collaborator_id))


@main_blueprint.get("/api/admin/analytics/collaborators")
@role_required("administrador", "chefe_sala")
def admin_collaborator_analytics():
    period = request.args.get("period", "month")
    return jsonify({"period": period, "ranking": get_collaborator_rankings(period)})


@main_blueprint.get("/api/admin/collaborators/<int:collaborator_id>/performance")
@role_required("administrador", "chefe_sala")
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


@main_blueprint.get("/api/management/collaborators")
@role_required("administrador", "chefe_sala")
def management_collaborators():
    return jsonify({"collaborators": list_manageable_collaborators()})


@main_blueprint.post("/api/management/collaborators")
@role_required("administrador", "chefe_sala")
def management_create_collaborator():
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404

    created, credentials, errors = create_collaborator_account(
        collaborator,
        request.get_json(silent=True) or {},
    )
    if errors:
        return jsonify({"message": "Falha ao cadastrar colaborador.", "errors": errors}), 400

    return jsonify(
        {
            "message": "Colaborador cadastrado com sucesso.",
            "collaborator": created.to_public_dict(),
            "credentials": credentials,
        }
    ), 201


@main_blueprint.put("/api/management/collaborators/<int:collaborator_id>")
@role_required("administrador", "chefe_sala")
def management_update_collaborator(collaborator_id):
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404

    updated, credentials, errors = update_collaborator_account(
        collaborator,
        collaborator_id,
        request.get_json(silent=True) or {},
    )
    if errors:
        return jsonify({"message": "Falha ao atualizar colaborador.", "errors": errors}), 400

    response = {
        "message": "Colaborador atualizado com sucesso.",
        "collaborator": updated.to_public_dict(),
    }
    if credentials:
        response["credentials"] = credentials
    return jsonify(response)


@main_blueprint.delete("/api/management/collaborators/<int:collaborator_id>")
@role_required("administrador", "chefe_sala")
def management_delete_collaborator(collaborator_id):
    collaborator = get_current_collaborator()
    if collaborator is None:
        return jsonify({"message": "Usuario autenticado nao encontrado."}), 404

    action, errors = delete_collaborator_account(collaborator, collaborator_id)
    if errors:
        return jsonify({"message": "Falha ao apagar colaborador.", "errors": errors}), 400

    if action == "deactivated":
        return jsonify(
            {
                "message": "Colaborador desativado porque possui historico operacional.",
                "action": action,
            }
        )
    return jsonify({"message": "Colaborador removido com sucesso.", "action": action})


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