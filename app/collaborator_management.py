import random
import string

from app.db import db
from app.models import Collaborator


MANAGEABLE_ROLES = {"colaborador", "chefe_sala"}


def normalize_access_code(value):
    return "".join(character for character in (value or "").upper() if character.isalnum())


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
        return target_role == "colaborador"
    return False


def create_collaborator_account(actor, payload):
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    role = (payload.get("role") or "colaborador").strip().lower()
    errors = {}

    if not name:
        errors["name"] = "Informe o nome do colaborador."
    if not email:
        errors["email"] = "Informe o email do colaborador."
    if role not in MANAGEABLE_ROLES:
        errors["role"] = "Perfil invalido para cadastro."
    elif not _can_assign_role(actor, role):
        errors["role"] = "Voce nao tem permissao para cadastrar este perfil."

    if email and Collaborator.query.filter_by(email=email).first() is not None:
        errors["email"] = "Ja existe um colaborador com este email."

    if errors:
        return None, None, errors

    access_code = generate_unique_access_code()
    pin = generate_numeric_pin()

    collaborator = Collaborator(
        name=name,
        email=email,
        role=role,
        active=True,
        access_code=access_code,
    )
    collaborator.set_password(pin)
    collaborator.set_pin(pin)

    db.session.add(collaborator)
    db.session.commit()

    return collaborator, {"access_code": access_code, "pin": pin}, None