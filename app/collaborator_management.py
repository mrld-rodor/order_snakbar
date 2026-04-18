import random
import string

from app.db import db
from app.models import Collaborator


MANAGEABLE_ROLES = {"colaborador", "chefe_sala"}


def normalize_access_code(value):
    return "".join(character for character in (value or "").upper() if character.isalnum())


def normalize_contact(value):
    return (value or "").strip().lower()


def generate_unique_access_code():
    for _ in range(200):
        candidate = "".join(random.choices(string.ascii_uppercase, k=3)) + "".join(
            random.choices(string.digits, k=2)
        )
        if Collaborator.query.filter_by(access_code=candidate).first() is None:
            return candidate
    raise RuntimeError("Nao foi possivel gerar um codigo de acesso unico.")


def generate_numeric_pin():
    return f"{random.randint(0, 9999):04d}"


def ensure_collaborator_access(collaborator):
    generated_pin = None
    changed = False

    if collaborator.role != "administrador" and not collaborator.access_code:
        collaborator.access_code = generate_unique_access_code()
        changed = True

    if collaborator.role != "administrador" and (not collaborator.pin_hash or not collaborator.pin_code):
        generated_pin = generate_numeric_pin()
        collaborator.set_pin(generated_pin)
        changed = True

    return changed, generated_pin


def list_manageable_collaborators():
    collaborators = (
        Collaborator.query.filter(Collaborator.role.in_(tuple(sorted(MANAGEABLE_ROLES))))
        .order_by(Collaborator.role.asc(), Collaborator.name.asc())
        .all()
    )
    return [collaborator.to_public_dict() for collaborator in collaborators]


def _can_assign_role(actor, target_role):
    if actor is None:
        return True
    if actor.role == "administrador":
        return target_role in MANAGEABLE_ROLES
    if actor.role == "chefe_sala":
        return target_role in MANAGEABLE_ROLES
    return False


def create_collaborator_account(actor, payload):
    name = (payload.get("name") or "").strip()
    contact = normalize_contact(payload.get("contact") or payload.get("email"))
    role = (payload.get("role") or "colaborador").strip().lower()
    errors = {}

    if not name:
        errors["name"] = "Informe o nome do colaborador."
    if not contact:
        errors["contact"] = "Informe o contacto do colaborador."
    if role not in MANAGEABLE_ROLES:
        errors["role"] = "Perfil invalido para cadastro."
    elif not _can_assign_role(actor, role):
        errors["role"] = "Voce nao tem permissao para cadastrar este perfil."

    if contact and Collaborator.query.filter_by(email=contact).first() is not None:
        errors["contact"] = "Ja existe um colaborador com este contacto."

    if errors:
        return None, None, errors

    access_code = generate_unique_access_code()
    pin = generate_numeric_pin()

    collaborator = Collaborator(
        name=name,
        contact=contact,
        role=role,
        active=True,
        access_code=access_code,
    )
    collaborator.set_password(pin)
    collaborator.set_pin(pin)

    db.session.add(collaborator)
    db.session.commit()

    return collaborator, {"access_code": access_code, "pin": pin}, None


def update_collaborator_account(actor, collaborator_id, payload):
    if actor is None or actor.role not in {"administrador", "chefe_sala"}:
        return None, None, {"permission": "Apenas administrador e chefia podem editar colaboradores."}

    collaborator = Collaborator.query.get(collaborator_id)
    if collaborator is None:
        return None, None, {"collaborator": "Colaborador nao encontrado."}

    name = (payload.get("name") or "").strip()
    contact = normalize_contact(payload.get("contact") or payload.get("email"))
    role = (payload.get("role") or collaborator.role).strip().lower()
    active = payload.get("active")
    errors = {}

    if not name:
        errors["name"] = "Informe o nome do colaborador."
    if not contact:
        errors["contact"] = "Informe o contacto do colaborador."
    if role not in MANAGEABLE_ROLES:
        errors["role"] = "Perfil invalido para edicao."
    elif not _can_assign_role(actor, role):
        errors["role"] = "Voce nao tem permissao para atribuir este perfil."

    existing = Collaborator.query.filter_by(email=contact).first() if contact else None
    if existing is not None and existing.id != collaborator.id:
        errors["contact"] = "Ja existe um colaborador com este contacto."

    if errors:
        return None, None, errors

    collaborator.name = name
    collaborator.contact = contact
    collaborator.role = role
    if active is not None:
        collaborator.active = bool(active)
    changed, generated_pin = ensure_collaborator_access(collaborator)

    db.session.commit()
    credentials = None
    if changed and generated_pin:
        credentials = {"access_code": collaborator.access_code, "pin": generated_pin}

    return collaborator, credentials, None


def delete_collaborator_account(actor, collaborator_id):
    if actor is None or actor.role not in {"administrador", "chefe_sala"}:
        return None, {"permission": "Apenas administrador e chefia podem apagar colaboradores."}

    collaborator = Collaborator.query.get(collaborator_id)
    if collaborator is None:
        return None, {"collaborator": "Colaborador nao encontrado."}
    if actor.id == collaborator.id:
        return None, {"collaborator": "Nao e permitido apagar a propria conta por esta tela."}

    if collaborator.orders or collaborator.payments:
        collaborator.active = False
        db.session.commit()
        return "deactivated", None

    db.session.delete(collaborator)
    db.session.commit()
    return "deleted", None