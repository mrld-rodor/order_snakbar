from functools import wraps

from flask import current_app, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.models import Collaborator


def authenticate_user(email, password):
    user = Collaborator.query.filter_by(email=email.lower(), active=True).first()
    if user is None:
        return None
    if not user.check_password(password):
        return None
    return public_user_data(user)


def public_user_data(user):
    return user.to_public_dict()


def get_current_collaborator():
    identity = get_jwt_identity()
    if identity is None:
        return None
    return Collaborator.query.get(int(identity))


def role_required(*allowed_roles):
    def decorator(view_function):
        @wraps(view_function)
        @jwt_required()
        def wrapped_view(*args, **kwargs):
            role = get_jwt().get("role")
            if role not in allowed_roles:
                return jsonify({"message": "Acesso negado para este perfil."}), 403
            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator