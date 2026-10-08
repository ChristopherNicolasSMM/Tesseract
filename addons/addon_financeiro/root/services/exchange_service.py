"""Conversão explícita para moeda-base; sem taxa automática ou efeito no estoque."""
import json
import logging
import re
from datetime import date
from decimal import Decimal, localcontext
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from core.db import db
from services.core.organization_service import Result
from addons.addon_financeiro.root.model.monetary import Currency
from addons.addon_financeiro.root.model.exchange import ExchangeRate, MonetaryConversion
from .monetary_service import resolve_policy, ROUNDINGS
logger = logging.getLogger(__name__)

def text(value, limit, name):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
        raise ValueError(f'{name}: informe texto de 1 a {limit} caracteres.')
    return value.strip()

def day(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise ValueError('Data: use AAAA-MM-DD.')
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('Data inválida.') from exc

def decimal_text(value, *, positive=False):
    if not isinstance(value, (str, Decimal)):
        raise ValueError('Valor deve ser texto decimal ou Decimal, nunca float.')
    if isinstance(value, str) and not re.fullmatch(r'-?[0-9]{1,18}(?:\.[0-9]{1,12})?', value):
        raise ValueError('Decimal inválido: até 18 inteiros e 12 fracionários, com ponto.')
    number = Decimal(value)
    if not number.is_finite() or number.copy_abs() >= Decimal('1e18') or not -12 <= number.as_tuple().exponent <= 18 or (positive and number <= 0):
        raise ValueError('Decimal fora dos limites ou taxa não positiva.')
    if number == 0: number = number.copy_abs()
    return format(number, 'f')

def create_rate(data, *, actor):
    try:
        required = {'organization_code', 'source_currency', 'target_currency', 'rate', 'valid_on', 'source', 'rate_type'}
        if not isinstance(data, dict) or set(data) != required:
            raise ValueError('Informe organização, par, taxa, data, fonte e tipo.')
        policy = resolve_policy(data['organization_code'])
        for key in ('source_currency', 'target_currency'):
            code = data[key]
            if not isinstance(code, str) or not re.fullmatch(r'[A-Z]{3}', code) or db.session.get(Currency, code) is None:
                raise ValueError('Moeda não cadastrada.')
        if data['source_currency'] == data['target_currency']: raise ValueError('Taxa deve ter moedas diferentes.')
        if data['target_currency'] != policy['currency_code']: raise ValueError('Destino deve ser a moeda-base da organização.')
        if data['rate_type'] not in ('MANUAL', 'CONTRACTUAL'): raise ValueError('Tipo deve ser MANUAL ou CONTRACTUAL.')
        obj = ExchangeRate(organization_code=policy['organization_code'], source_currency=data['source_currency'], target_currency=data['target_currency'], rate=decimal_text(data['rate'], positive=True), valid_on=day(data['valid_on']), source=text(data['source'], 120, 'Fonte'), rate_type=data['rate_type'], created_by=text(actor, 120, 'Autor'))
        db.session.add(obj); db.session.commit()
        return Result(True, data=obj.to_dict(), code=201)
    except ValueError as exc: return Result(False, error=str(exc), code=422)
    except SQLAlchemyError:
        db.session.rollback(); logger.exception('Falha ao registrar taxa')
        return Result(False, error='Falha ao salvar taxa; nenhuma alteração confirmada.', code=409)

def preview_conversion(data):
    required = {'organization_code', 'source_currency', 'amount', 'operation_date', 'rate_id'}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError('Informe organização, moeda original, valor, data da operação e taxa (ou null).')
    policy = resolve_policy(data['organization_code'])
    currency = data['source_currency']
    if not isinstance(currency, str) or db.session.get(Currency, currency) is None: raise ValueError('Moeda original não cadastrada.')
    original = decimal_text(data['amount']); operation_date = day(data['operation_date']); rate = None
    if currency == policy['currency_code']:
        if data['rate_id'] is not None: raise ValueError('Operação na moeda-base não utiliza taxa.')
        factor = Decimal(1)
    else:
        if type(data['rate_id']) is not int or data['rate_id'] <= 0: raise ValueError('Escolha uma taxa explícita; não há paridade ou inversão automática.')
        obj = db.session.get(ExchangeRate, data['rate_id'], populate_existing=True)
        if obj is None or obj.organization_code != policy['organization_code'] or obj.source_currency != currency or obj.target_currency != policy['currency_code']: raise ValueError('Taxa não pertence à organização ou ao par solicitado.')
        if obj.valid_on != operation_date: raise ValueError('Data da taxa deve coincidir com a data da operação.')
        rate = obj.to_dict(); factor = Decimal(rate['rate'])
    with localcontext() as context:
        context.prec = 64
        product = Decimal(original) * factor
        if product.copy_abs() >= Decimal('1e18'): raise ValueError('Conversão excede a magnitude suportada.')
        converted = product.quantize(Decimal(1).scaleb(-policy['decimal_places']), rounding=ROUNDINGS[policy['rounding']])
        if converted.copy_abs() >= Decimal('1e18'): raise ValueError('Arredondamento excede a magnitude suportada.')
        if converted == 0: converted = converted.copy_abs()
    return {'organization_code': policy['organization_code'], 'source_currency': currency, 'original_amount': original, 'target_currency': policy['currency_code'], 'converted_amount': format(converted, 'f'), 'unrounded_amount': format(product, 'f'), 'operation_date': operation_date.isoformat(), 'rate': rate, 'policy': policy}

def confirm_conversion(data, *, actor):
    try:
        required = {'organization_code', 'source_currency', 'amount', 'operation_date', 'rate_id', 'idempotency_key', 'reference'}
        if not isinstance(data, dict) or set(data) != required: raise ValueError('Informe dados de conversão, referência e chave de idempotência.')
        key = text(data['idempotency_key'], 80, 'Chave de idempotência'); reference = text(data['reference'], 120, 'Referência'); actor = text(actor, 120, 'Autor')
        snapshot = preview_conversion({k: v for k, v in data.items() if k not in {'idempotency_key', 'reference'}})
        existing = MonetaryConversion.query.filter_by(organization_code=snapshot['organization_code'], idempotency_key=key).first()
        if existing:
            if existing.to_dict()['snapshot'] != snapshot or existing.reference != reference: return Result(False, error='Chave já utilizada com dados diferentes.', code=409)
            return Result(True, data=existing.to_dict(), code=200)
        obj = MonetaryConversion(organization_code=snapshot['organization_code'], idempotency_key=key, reference=reference, snapshot=json.dumps(snapshot, ensure_ascii=False, sort_keys=True), created_by=actor)
        db.session.add(obj); db.session.commit()
        return Result(True, data=obj.to_dict(), code=201)
    except ValueError as exc: return Result(False, error=str(exc), code=422)
    except IntegrityError:
        db.session.rollback()
        existing = MonetaryConversion.query.filter_by(organization_code=snapshot['organization_code'], idempotency_key=key).first()
        if existing and existing.to_dict()['snapshot'] == snapshot and existing.reference == reference: return Result(True, data=existing.to_dict(), code=200)
        return Result(False, error='Conflito de confirmação; nenhuma duplicação realizada.', code=409)
    except SQLAlchemyError:
        db.session.rollback(); logger.exception('Falha ao confirmar conversão')
        return Result(False, error='Falha ao salvar conversão; nenhuma alteração confirmada.', code=409)
