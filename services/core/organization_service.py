"""Cadastro manual e contrato público de identidade para futuros addons."""
from dataclasses import dataclass
import logging
import re
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from core.db import db
from model.core.organization import Organization, PROFILE_FIELDS
from model.core.organization_contact import OrganizationContact
from core.document_validation import DocumentValidator

logger = logging.getLogger(__name__)


@dataclass
class Result:
    success: bool
    data: object = None
    error: str | None = None
    code: int = 200


def resolve_organization(ident, *, require_active=True):
    """Leitura em processo; chamador aplica autorização e guarda o ID estável."""
    if isinstance(ident, bool) or not isinstance(ident, int) or ident <= 0:
        raise ValueError('Identificador de organização inválido.')
    obj = db.session.get(Organization, ident, populate_existing=True)
    if obj is None or (require_active and not obj.is_active):
        raise ValueError('Organização ausente ou inativa.')
    return obj.to_dict()


def list_organizations(search=''):
    query = Organization.query
    if search:
        pattern = f'%{search}%'
        query = query.filter(db.or_(Organization.name.ilike(pattern), Organization.code.ilike(pattern)))
    return query.order_by(Organization.name, Organization.id).all()


def save_organization(data, ident=None):
    try:
        if ident is not None and (isinstance(ident, bool) or not isinstance(ident, int) or ident <= 0):
            return Result(False, error='Identificador de organização inválido.', code=422)
        if not isinstance(data, dict) or set(data) - ({'code', 'name', 'is_active'} | set(PROFILE_FIELDS)):
            return Result(False, error='Dados ou campos inválidos.', code=422)
        obj = db.session.get(Organization, ident) if ident is not None else Organization()
        if obj is None:
            return Result(False, error='Organização não encontrada.', code=404)
        code = data.get('code', obj.code)
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{0,39}', code.strip().upper()):
            return Result(False, error='Código: 1–40 caracteres, letras ASCII, números, hífen ou sublinhado.', code=422)
        code = code.strip().upper()
        if ident is not None and code != obj.code:
            return Result(False, error='O código da organização é imutável.', code=409)
        name = data.get('name', obj.name)
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            return Result(False, error='Nome deve ter entre 1 e 120 caracteres.', code=422)
        active = data.get('is_active', obj.is_active if ident is not None else True)
        if not isinstance(active, bool):
            return Result(False, error='Estado ativo deve ser booleano.', code=422)
        profile = validate_profile(data)
        obj.code, obj.name, obj.is_active = code, name.strip(), active
        for field, value in profile.items():
            setattr(obj, field, value)
        if ident is None:
            db.session.add(obj)
        db.session.commit()
        return Result(True, data=obj.to_dict(), code=201 if ident is None else 200)
    except ValueError as exc:
        return Result(False, error=str(exc), code=422)
    except IntegrityError:
        db.session.rollback()
        return Result(False, error='Já existe organização com esse código ou CNPJ.', code=409)
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception('Falha ao manter organização')
        return Result(False, error='Não foi possível salvar. Nenhuma alteração foi confirmada.', code=409)


def resolve_organization_by_code(code, *, require_active=True):
    """Chave de negócio para referências fracas; não exige FK entre módulos."""
    if not isinstance(code, str) or not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{0,39}', code.strip().upper()):
        raise ValueError('Código de organização inválido.')
    obj = Organization.query.filter_by(code=code.strip().upper()).populate_existing().first()
    if obj is None or (require_active and not obj.is_active):
        raise ValueError('Organização ausente ou inativa.')
    return obj.to_dict()


BRAZIL_STATES = set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())


def validate_profile(data):
    clean = {}
    for field, limit in PROFILE_FIELDS.items():
        if field not in data:
            continue
        value = data[field]
        if value is None or value == '':
            clean[field] = None
            continue
        if not isinstance(value, str):
            raise ValueError(f'{field}: texto esperado.')
        value = value.strip()
        if not value:
            clean[field] = None
            continue
        validator = getattr(DocumentValidator, field, None)
        if field in {'cnpj', 'cep', 'email', 'phone'}:
            value = validator(value)
        if field == 'estado':
            value = value.upper()
            if value not in BRAZIL_STATES:
                raise ValueError('UF brasileira inválida.')
        if len(value) > limit:
            raise ValueError(f'{field}: máximo de {limit} caracteres.')
        if field == 'website' and not re.fullmatch(r'https?://[^\s]+', value):
            raise ValueError('Site deve começar com http:// ou https://.')
        clean[field] = value
    return clean


def save_organization_contact(organization_id, data, ident=None):
    """Novo responsável ou edição/inativação explícita. Sem exclusão física."""
    try:
        resolve_organization(organization_id, require_active=False)
        if ident is not None and (isinstance(ident, bool) or not isinstance(ident, int) or ident <= 0):
            raise ValueError('Identificador de responsável inválido.')
        allowed = {'name', 'role', 'cpf', 'email', 'phone', 'is_active'}
        if not isinstance(data, dict) or set(data) - allowed:
            raise ValueError('Dados do responsável inválidos.')
        obj = db.session.get(OrganizationContact, ident) if ident is not None else OrganizationContact(organization_id=organization_id)
        if obj is None or obj.organization_id != organization_id:
            return Result(False, error='Responsável não encontrado nesta organização.', code=404)
        clean = {}
        for field, limit in {'name': 120, 'role': 80}.items():
            value = data.get(field, getattr(obj, field))
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
                raise ValueError(f'{field}: obrigatório, até {limit} caracteres.')
            clean[field] = value.strip()
        for field in ('cpf', 'email', 'phone'):
            if field in data:
                value = data[field]
                clean[field] = None if value is None or value == '' else getattr(DocumentValidator, field)(value)
        active = data.get('is_active', obj.is_active if ident else True)
        if not isinstance(active, bool):
            raise ValueError('Estado ativo deve ser booleano.')
        for field, value in clean.items():
            setattr(obj, field, value)
        obj.is_active = active
        if ident is None:
            db.session.add(obj)
        db.session.commit()
        return Result(True, data=obj.to_dict(), code=201 if ident is None else 200)
    except ValueError as exc:
        return Result(False, error=str(exc), code=422)
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception('Falha ao manter responsável')
        return Result(False, error='Não foi possível salvar o responsável. Nenhuma alteração confirmada.', code=409)
