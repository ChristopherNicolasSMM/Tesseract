"""Retirada do legado e entrada organizacional com prévia conferida e auditoria."""
import hashlib
import json
from decimal import Decimal
from core.db import db
from . import estoque_service
from .material_unit_integrity_service import reserve_material
from .financial_stock_contract import text, decimal_text, preview_conversion
from .organization_stock_service import dump, _record
from ..model.saldo import Saldo
from ..model.movimentacao import Movimentacao
from ..model.organization_stock import OrganizationMovement

FIELDS = {'organization_code', 'material_id', 'quantity', 'source_currency', 'source_amount',
          'operation_date', 'rate_id', 'policy_version_id', 'idempotency_key', 'reason'}


def _data(data):
    if not isinstance(data, dict) or set(data) != FIELDS:
        raise ValueError('Campos de reconciliação inválidos.')
    if type(data['material_id']) is not int or data['material_id'] <= 0:
        raise ValueError('Material inválido.')
    return {**data, 'quantity': decimal_text(data['quantity'], positive=True),
        'source_amount': decimal_text(data['source_amount']),
        'idempotency_key': text(data['idempotency_key'], 60, 'Referência'),
        'reason': text(data['reason'], 1000, 'Justificativa')}


def _source(material_id):
    saldo = Saldo.query.filter_by(material_id=material_id, is_deleted=False).populate_existing().first()
    latest = Movimentacao.query.filter_by(material_id=material_id).order_by(Movimentacao.id.desc()).first()
    if saldo is None:
        raise ValueError('Material sem saldo legado.')
    return {'saldo_id': saldo.id, 'quantity': str(saldo.quantidade_atual),
            'stock_value': str(saldo.valor_total_estoque), 'average': str(saldo.custo_medio),
            'latest_movement_id': latest.id if latest else None}


def preview(data):
    data = _data(data)
    if Decimal(data['source_amount']) < 0:
        raise ValueError('Avaliação não pode ser negativa; informe zero explicitamente se aplicável.')
    from services.core.organization_service import resolve_organization_by_code
    data['organization_code'] = resolve_organization_by_code(data['organization_code'])['code']
    source = _source(data['material_id'])
    quantity = Decimal(data['quantity'])
    if quantity > Decimal(source['quantity']):
        raise ValueError('Quantidade superior ao saldo legado disponível.')
    # A origem é Float; rejeitar quantidade não representável em vez de perder unidades.
    if Decimal(str(float(quantity))) != quantity:
        raise ValueError('Quantidade não representável pelo estoque legado; reduza a precisão explicitamente.')
    conversion = preview_conversion({'organization_code': data['organization_code'],
        'source_currency': data['source_currency'], 'amount': data['source_amount'],
        'operation_date': data['operation_date'], 'rate_id': data['rate_id'],
        'policy_version_id': data['policy_version_id']})
    plan = {'request': data, 'source': source, 'conversion': conversion}
    return {**plan, 'preview_token': hashlib.sha256(dump(plan).encode()).hexdigest()}


def confirm(data, token, *, actor):
    try:
        data = _data(data)
        actor = text(actor, 120, 'Autor')
        token = text(token, 64, 'Token de prévia')
        reserve_material(data['material_id'])
        from services.core.organization_service import resolve_organization_by_code
        data['organization_code'] = resolve_organization_by_code(data['organization_code'])['code']
        key = 'reconcile:' + data['idempotency_key']
        previous = OrganizationMovement.query.filter_by(organization_code=data['organization_code'], idempotency_key=key).first()
        if previous:
            snapshot = json.loads(previous.snapshot_json)
            if snapshot.get('reconciliation', {}).get('request') != data or snapshot['reconciliation']['preview_token'] != token:
                raise ValueError('Referência de reconciliação já utilizada com outros dados.')
            db.session.rollback()
            return {'movimentacao': previous.to_dict(), 'replayed': True}
        plan = preview(data)
        if plan['preview_token'] != token:
            raise ValueError('Prévia desatualizada; confira novamente antes de confirmar.')
        legacy = estoque_service._registrar_movimentacao_legada(data['material_id'], 'saida', float(data['quantity']),
            observacoes=f'Reconciliação para {data["organization_code"]}: {data["idempotency_key"]}. {data["reason"]}', commit=False)
        remaining = Decimal(str(legacy['saldo']['quantidade_atual']))
        if Decimal(plan['source']['quantity']) - remaining != Decimal(data['quantity']):
            raise ValueError('Precisão do saldo legado impede esta retirada exata; confira o inventário.')
        plan['legacy_movement_id'] = legacy['movimentacao']['id']
        conversion = plan['conversion']
        result = _record(organization_code=data['organization_code'], material_id=data['material_id'], kind='entrada',
            quantity=Decimal(data['quantity']), value=Decimal(conversion['converted_amount']), policy=conversion['policy'],
            request=data, snapshot={'reconciliation': plan, 'conversion': conversion}, actor=actor, key=key, commit=False)
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise
