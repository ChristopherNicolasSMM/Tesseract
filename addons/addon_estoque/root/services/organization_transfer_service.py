"""Transferência pareada; escrita somente pela regra central de movimentação."""
import hashlib
import json
from decimal import Decimal
from core.db import db
from services.core.organization_service import resolve_organization_by_code
from addons.addon_estoque.root.model.organization_stock import OrganizationMovement
from .financial_stock_contract import text, day, resolve_selected_policy, preview_conversion
from .material_unit_integrity_service import reserve_material
from .organization_stock_service import number, canonical, dump, _record

MARKER = 'organization_stock_transfer'
FIELDS = {'source_organization', 'destination_organization', 'material_id', 'quantity', 'operation_date',
          'source_policy_version_id', 'destination_policy_version_id', 'rate_id', 'idempotency_key', 'notes'}


def _response(reference, outgoing, incoming, replayed):
    return {'transfer_reference': reference, 'saida': outgoing, 'entrada': incoming, 'replayed': replayed}


def transfer(data, *, actor):
    """Chamado por estoque_service.transferir_entre_organizacoes, que garante rollback."""
    try:
        return _transfer(data, actor=actor)
    except Exception:
        db.session.rollback()
        raise


def _transfer(data, *, actor):
    from . import estoque_service
    if not isinstance(data, dict) or set(data) != FIELDS:
        raise ValueError('Informe origem, destino, material, quantidade, data, políticas, taxa, referência e observações.')
    actor = text(actor, 120, 'Autor')
    source = resolve_organization_by_code(data['source_organization'], require_active=False)
    target = resolve_organization_by_code(data['destination_organization'], require_active=False)
    if source['code'] == target['code']:
        raise ValueError('Origem e destino devem ser organizações diferentes.')
    if type(data['material_id']) is not int or not 1 <= data['material_id'] <= 2147483647:
        raise ValueError('Material inválido.')
    quantity = number(data['quantity'], positive=True)
    date = day(data['operation_date']).isoformat()
    key = text(data['idempotency_key'], 80, 'Referência da transferência')
    notes = data['notes']
    if notes is not None and (not isinstance(notes, str) or len(notes) > 1000):
        raise ValueError('Observações: no máximo 1000 caracteres.')
    for field in ('source_policy_version_id', 'destination_policy_version_id', 'rate_id'):
        if data[field] is not None and (type(data[field]) is not int or not 1 <= data[field] <= 2147483647):
            raise ValueError('Taxa e versões devem ser identificadores positivos ou null.')
    request = data | {'source_organization': source['code'], 'destination_organization': target['code'],
                      'quantity': canonical(quantity), 'operation_date': date, 'idempotency_key': key}
    reference = 'transfer:' + hashlib.sha256(dump([source['code'], key]).encode('utf-8')).hexdigest()
    # A mesma reserva do estoque normal serializa inclusive transferências inversas.
    reserve_material(data['material_id'])
    rows = OrganizationMovement.query.filter(OrganizationMovement.idempotency_key.in_(
        [reference + ':out', reference + ':in'])).populate_existing().all()
    if rows:
        outgoing = next((row for row in rows if row.organization_code == source['code'] and row.idempotency_key.endswith(':out')), None)
        incoming = next((row for row in rows if row.idempotency_key.endswith(':in')), None)
        if outgoing is None or incoming is None:
            raise ValueError('Histórico incompleto de transferência; nenhuma nova perna será registrada.')
        if (outgoing.request_json != dump(request | {'role': 'out'})
            or incoming.request_json != dump(request | {'role': 'in'})
            or incoming.organization_code != target['code']):
            raise ValueError('Referência de transferência já utilizada com dados diferentes.')
        result = _response(reference,
            {'movimentacao': outgoing.to_dict(), 'saldo': json.loads(outgoing.snapshot_json)['saldo_after'], 'replayed': True},
            {'movimentacao': incoming.to_dict(), 'saldo': json.loads(incoming.snapshot_json)['saldo_after'], 'replayed': True}, True)
        db.session.rollback()
        return result
    if not source['is_active'] or not target['is_active']:
        raise ValueError('Transferência exige duas organizações ativas.')
    source_policy = resolve_selected_policy(source['code'], policy_version_id=data['source_policy_version_id'], operation_date=date)
    target_policy = resolve_selected_policy(target['code'], policy_version_id=data['destination_policy_version_id'], operation_date=date)
    if MARKER in db.session.info:
        raise ValueError('Transferência já em andamento nesta transação.')
    state = {'reference': reference, 'request': request, 'actor': actor, 'quantity': quantity,
             'source_policy': source_policy, 'target_policy': target_policy, 'stage': 0}
    db.session.info[MARKER] = state
    try:
        outgoing = estoque_service.registrar_movimentacao(data['material_id'], 'saida', canonical(quantity),
            organization_code=source['code'], actor=actor, transfer_reference=reference, commit=False)
        value = -Decimal(outgoing['movimentacao']['custo_total'])
        if source_policy['currency_code'] == target_policy['currency_code']:
            if data['rate_id'] is not None:
                raise ValueError('Transferência na mesma moeda não utiliza taxa.')
            # Transportar valor contábil exato; não arredondar novamente na organização destino.
            state['incoming_value'] = value
            state['conversion'] = None
        else:
            conversion = preview_conversion({'organization_code': target['code'],
                'source_currency': source_policy['currency_code'], 'amount': canonical(value),
                'operation_date': date, 'rate_id': data['rate_id'],
                'policy_version_id': data['destination_policy_version_id']})
            state['incoming_value'] = Decimal(conversion['converted_amount'])
            state['conversion'] = conversion
        state['outgoing_id'] = outgoing['movimentacao']['id']
        state['outgoing_value'] = canonical(value)
        incoming = estoque_service.registrar_movimentacao(data['material_id'], 'entrada', canonical(quantity),
            organization_code=target['code'], actor=actor, transfer_reference=reference, commit=False)
        if state['stage'] != 2:
            raise ValueError('Transferência incompleta.')
        db.session.commit()
        return _response(reference, outgoing, incoming, False)
    finally:
        db.session.info.pop(MARKER, None)


def register_leg(reference, *, organization_code, material_id, kind, quantity, actor, commit):
    state = db.session.info.get(MARKER)
    if state is None or reference != state['reference'] or commit or actor != state['actor']:
        raise ValueError('Use transferir_entre_organizacoes para confirmar saída e entrada juntas.')
    request = state['request']
    role = 'out' if state['stage'] == 0 else 'in' if state['stage'] == 1 else None
    expected_org = request['source_organization'] if role == 'out' else request['destination_organization']
    if (role is None or material_id != request['material_id'] or organization_code != expected_org
        or kind != ('saida' if role == 'out' else 'entrada') or number(quantity, positive=True) != state['quantity']):
        raise ValueError('Perna de transferência incompatível com a operação em andamento.')
    snapshot = {'transfer_reference': reference, 'transfer_role': role,
                'source_organization': request['source_organization'], 'destination_organization': request['destination_organization'],
                'operation_date': request['operation_date'], 'observacoes': request['notes']}
    if role == 'in':
        snapshot.update(outgoing_movement_id=state['outgoing_id'], outgoing_value=state['outgoing_value'],
            source_currency=state['source_policy']['currency_code'], conversion=state['conversion'],
            same_currency_cost_carried=state['conversion'] is None)
    result = _record(organization_code=organization_code, material_id=material_id, kind=kind,
        quantity=-state['quantity'] if role == 'out' else state['quantity'],
        value=None if role == 'out' else state['incoming_value'],
        policy=state['source_policy'] if role == 'out' else state['target_policy'],
        request=request | {'role': role}, snapshot=snapshot, actor=actor, key=reference + ':' + role, commit=False)
    state['stage'] += 1
    return result
