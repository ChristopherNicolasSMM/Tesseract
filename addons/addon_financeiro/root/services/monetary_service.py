"""Políticas explícitas e arredondamento Decimal; não movimenta estoque."""
import logging
import re
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP, ROUND_HALF_EVEN
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from core.db import db
from services.core.organization_service import Result, resolve_organization_by_code
from addons.addon_financeiro.root.model.monetary import Currency, MonetaryPolicy

logger = logging.getLogger(__name__)
ROUNDINGS = {'HALF_UP': ROUND_HALF_UP, 'HALF_EVEN': ROUND_HALF_EVEN}


def create_currency(data):
    try:
        if not isinstance(data, dict) or set(data) != {'code', 'name', 'decimal_places'}:
            raise ValueError('Informe código, nome e casas decimais da moeda.')
        code, name, places = data['code'], data['name'], data['decimal_places']
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z]{3}', code):
            raise ValueError('Código de moeda: três letras ASCII maiúsculas.')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError('Nome da moeda: 1–80 caracteres.')
        if type(places) is not int or not 0 <= places <= 6:
            raise ValueError('Casas decimais: inteiro de zero a seis.')
        obj = Currency(code=code, name=name.strip(), decimal_places=places)
        db.session.add(obj)
        db.session.commit()
        return Result(True, data=obj.to_dict(), code=201)
    except ValueError as exc:
        return Result(False, error=str(exc), code=422)
    except IntegrityError:
        db.session.rollback()
        return Result(False, error='Moeda já cadastrada ou restrição violada.', code=409)
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception('Falha ao cadastrar moeda')
        return Result(False, error='Falha ao salvar moeda; nenhuma alteração confirmada.', code=409)


def create_policy(data):
    try:
        if not isinstance(data, dict) or set(data) != {'organization_code', 'currency_code', 'rounding'}:
            raise ValueError('Informe organização, moeda-base e arredondamento.')
        org = resolve_organization_by_code(data['organization_code'])
        currency_code = data['currency_code']
        if not isinstance(currency_code, str) or not re.fullmatch(r'[A-Z]{3}', currency_code):
            raise ValueError('Código de moeda inválido.')
        currency = db.session.get(Currency, currency_code, populate_existing=True)
        if currency is None:
            raise ValueError('Cadastre a moeda antes de configurar a organização.')
        rounding = data['rounding']
        if not isinstance(rounding, str) or rounding not in ROUNDINGS:
            raise ValueError('Escolha HALF_UP ou HALF_EVEN explicitamente.')
        obj = MonetaryPolicy(organization_code=org['code'], currency_code=currency.code,
                             decimal_places=currency.decimal_places, rounding=rounding)
        db.session.add(obj)
        db.session.commit()
        return Result(True, data=obj.to_dict(), code=201)
    except ValueError as exc:
        return Result(False, error=str(exc), code=422)
    except IntegrityError:
        db.session.rollback()
        return Result(False, error='A organização já possui política inicial. Alteração exige futura versão explícita.', code=409)
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception('Falha ao cadastrar política monetária')
        return Result(False, error='Falha ao salvar política; nenhuma alteração confirmada.', code=409)


def resolve_policy(organization_code):
    org = resolve_organization_by_code(organization_code)
    policy = MonetaryPolicy.query.filter_by(organization_code=org['code']).populate_existing().first()
    if policy is None:
        raise ValueError('Organização sem política monetária explícita.')
    return policy.to_dict()


def quantize_amount(amount, organization_code):
    """Contrato público: texto decimal ou Decimal -> texto e snapshot da política.

    Rejeita float/bool e magnitude fora de 18 dígitos inteiros/12 fracionários.
    Não é conversão cambial nem cálculo de preço por unidade de estoque.
    """
    policy = resolve_policy(organization_code)
    if not isinstance(amount, (str, Decimal)):
        raise ValueError('Valor deve ser texto decimal ou Decimal, nunca float.')
    if isinstance(amount, str) and not re.fullmatch(r'-?[0-9]{1,18}(?:\.[0-9]{1,12})?', amount):
        raise ValueError('Valor decimal inválido ou fora da precisão suportada.')
    try:
        value = Decimal(amount)
        if not value.is_finite() or value.copy_abs() >= Decimal('1e18') or value.as_tuple().exponent < -12:
            raise ValueError('Valor decimal inválido ou fora da precisão suportada.')
        with localcontext() as context:
            context.prec = 40
            value = value.quantize(Decimal(1).scaleb(-policy['decimal_places']), rounding=ROUNDINGS[policy['rounding']])
        if value.copy_abs() >= Decimal('1e18'):
            raise ValueError('Arredondamento excede a magnitude suportada.')
        if value == 0:
            value = value.copy_abs()
        return {'amount': format(value, 'f'), 'policy': policy}
    except InvalidOperation as exc:
        raise ValueError('Valor decimal inválido.') from exc
