"""Implementação Decimal chamada apenas pela regra central de movimentação."""
import json
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from core.db import db
from services.core.organization_service import resolve_organization_by_code
from .financial_stock_contract import decimal_text, preview_conversion, text, day, resolve_selected_policy, rounding
from addons.addon_estoque.root.model.organization_stock import OrganizationBalance, OrganizationMovement, OrderValuation
from .material_unit_integrity_service import reserve_material


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def number(value, *, positive=False):
    return Decimal(decimal_text(value, positive=positive))


def canonical(value):
    raw = format(value, 'f')
    return (raw.rstrip('0').rstrip('.') if '.' in raw else raw) if value else '0'


def _record(*, organization_code, material_id, kind, quantity, value, policy, request,
            snapshot, actor, key, commit, item_id=None, unit_id=None):
    if type(material_id) is not int or not 1 <= material_id <= 2147483647:
        raise ValueError('Material: identificador fora dos limites suportados.')
    material = reserve_material(material_id)
    if not material.unidade_medida:
        raise ValueError('Defina a unidade-base do material antes de movimentar por organização.')
    if not material.ativo:
        raise ValueError('Material inativo.')
    stored_request = dump(request)
    previous = OrganizationMovement.query.filter_by(organization_code=organization_code, idempotency_key=key).first()
    if previous:
        if previous.request_json != stored_request:
            raise ValueError('Chave de idempotência já utilizada com dados diferentes.')
        # Retorno original, inclusive o saldo após aquela operação, não o saldo atual.
        if commit:
            db.session.rollback()
        return {'movimentacao': previous.to_dict(), 'saldo': json.loads(previous.snapshot_json)['saldo_after'], 'replayed': True}
    balance = OrganizationBalance.query.filter_by(organization_code=organization_code, material_id=material_id).populate_existing().first()
    if balance is None:
        balance = OrganizationBalance(organization_code=organization_code, material_id=material_id,
                                      currency_code=policy['currency_code'], quantity=Decimal(0), stock_value=Decimal(0))
        db.session.add(balance)
    if balance.currency_code != policy['currency_code']:
        raise ValueError('Moeda-base incompatível com o saldo existente.')
    before = {'quantity': canonical(balance.quantity), 'value': canonical(balance.stock_value)}
    with localcontext() as ctx:
        ctx.prec = 64
        if quantity < 0:
            removed = -quantity
            if removed > balance.quantity:
                raise ValueError('Saldo insuficiente nesta organização; o saldo legado e de outras organizações não é utilizado.')
            value = -balance.stock_value if removed == balance.quantity else -(balance.stock_value * removed / balance.quantity).quantize(
                Decimal(1).scaleb(-policy['decimal_places']), rounding=rounding(policy))
            # Uma versão de menor precisão pode arredondar além do resíduo existente.
            value = max(value, -balance.stock_value)
        balance.quantity += quantity
        balance.stock_value += value
        if balance.quantity < 0 or balance.stock_value < 0 or balance.stock_value >= Decimal('1e18') or balance.quantity >= Decimal('1e18'):
            raise ValueError('Saldo fora da magnitude suportada.')
        if balance.quantity == 0:
            balance.stock_value = Decimal(0)
    balance.updated_at = datetime.now(timezone.utc)
    db.session.flush()
    snapshot = snapshot | {'unit_base': material.unidade_medida, 'policy': policy, 'saldo_before': before, 'saldo_after': balance.to_dict()}
    row = OrganizationMovement(organization_code=organization_code, material_id=material_id,
                               currency_code=policy['currency_code'], kind=kind, quantity_delta=quantity,
                               value_delta=value, idempotency_key=key, request_json=stored_request,
                               snapshot_json=dump(snapshot), created_by=actor,
                               pedido_compra_item_id=item_id, material_unidade_id=unit_id)
    db.session.add(row)
    try:
        db.session.commit() if commit else db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError('Conflito de idempotência ou recebimento já registrado; nenhuma duplicação confirmada.') from exc
    return {'movimentacao': row.to_dict(), 'saldo': snapshot['saldo_after'], 'replayed': False}


def register(data, *, actor, commit=True):
    required = {'organization_code','material_id','tipo_movimentacao','quantidade','custo_unitario',
                'source_currency','operation_date','rate_id','policy_version_id','idempotency_key','observacoes'}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError('Campos de movimentação organizacional inválidos.')
    actor = text(actor,120,'Autor')
    org = resolve_organization_by_code(data['organization_code'])
    key = text(data['idempotency_key'],80,'Chave de idempotência')
    if key.startswith(('receipt:', 'transfer:')):
        raise ValueError('Prefixo de idempotência reservado ao recebimento/transferência.')
    kind = data['tipo_movimentacao']
    if kind not in ('entrada','saida','ajuste'):
        raise ValueError('Tipo de movimentação inválido.')
    amount = number(data['quantidade'])
    if amount == 0 or (kind in ('entrada','saida') and amount < 0):
        raise ValueError('Quantidade deve ser positiva em entrada/saída e diferente de zero em ajuste.')
    quantity = -amount if kind == 'saida' else amount
    date = day(data['operation_date']).isoformat()
    notes = data['observacoes']
    if notes is not None and (not isinstance(notes,str) or len(notes) > 1000):
        raise ValueError('Observações: no máximo 1000 caracteres.')
    policy = resolve_selected_policy(org['code'],policy_version_id=data['policy_version_id'],operation_date=date)
    snapshot = {'observacoes':notes, 'conversion':None}
    value = None
    cost = None
    if quantity > 0:
        cost = number(data['custo_unitario'])
        if cost < 0:
            raise ValueError('Custo não pode ser negativo; informe zero explicitamente quando aplicável.')
        with localcontext() as ctx:
            ctx.prec = 64
            total = quantity * cost
        conversion = preview_conversion({'organization_code':org['code'],'source_currency':data['source_currency'],
            'amount':canonical(total),'operation_date':date,'rate_id':data['rate_id'],'policy_version_id':data['policy_version_id']})
        value = Decimal(conversion['converted_amount'])
        snapshot['conversion'] = conversion
    elif any(data[field] is not None for field in ('custo_unitario','source_currency','rate_id')):
        raise ValueError('Saída utiliza o custo do saldo; não informe custo, moeda original ou taxa.')
    request = data | {'organization_code':org['code'], 'idempotency_key':key, 'quantidade':canonical(amount),
                      'custo_unitario':canonical(cost) if cost is not None else None}
    return _record(organization_code=org['code'],material_id=data['material_id'],kind=kind,quantity=quantity,
                   value=value,policy=policy,request=request,snapshot=snapshot,actor=actor,key=key,commit=commit)


def register_valuation_line(valuation_id, item_id, *, material_id, quantity, actor, extra, commit=False):
    """Snapshot vem do banco imutável; não aceita conversão fornecida pelo cliente."""
    from .purchase_integrity_service import reserve_order
    from .purchase_context_service import get_context
    from .order_valuation_service import item_signature
    from addons.addon_estoque.root.model.item_pedido_compra import ItemPedidoCompra
    if type(valuation_id) is not int or valuation_id <= 0 or type(item_id) is not int or item_id <= 0:
        raise ValueError('Avaliação/item inválido.')
    plan = db.session.get(OrderValuation,valuation_id,populate_existing=True)
    if plan is None:
        raise ValueError('Avaliação monetária ausente.')
    if commit or db.session.info.get('organization_receipt_order') != plan.order_id:
        raise ValueError('Use receber_pedido_compra para confirmar o recebimento completo em uma transação.')
    order = reserve_order(plan.order_id)
    item = db.session.get(ItemPedidoCompra,item_id,populate_existing=True)
    if order is None or order.is_deleted or order.status != 'confirmado' or item is None or item.is_deleted or item.pedido_compra_id != order.id:
        raise ValueError('Recebimento exige pedido confirmado e item ativo da avaliação.')
    context = get_context('order',order.id)
    frozen = json.loads(plan.snapshot_json)
    if context is None or context.organization_code != frozen['organization_code']:
        raise ValueError('Contexto do pedido diverge da avaliação.')
    resolve_organization_by_code(context.organization_code)  # novo movimento exige organização ativa
    line = next((line for line in frozen['items'] if line['item']['id'] == item_id),None)
    if item.material_id != material_id or line is None or item_signature(item) != line['item'] or number(quantity,positive=True) != Decimal(line['quantity_base']):
        raise ValueError('Item diverge do snapshot monetário congelado.')
    conversion = line['conversion']
    policy = conversion['policy']
    actor = text(actor,120,'Autor')
    key = f'receipt:{order.id}:item:{item.id}'
    lot = extra.get('lote_fornecedor') or None
    expiry = extra.get('data_validade')
    if lot is not None and (not isinstance(lot,str) or len(lot) > 100):
        raise ValueError('Lote: no máximo 100 caracteres.')
    from datetime import date
    if expiry is not None and type(expiry) is not date:
        raise ValueError('Validade inválida.')
    request = {'valuation_id':valuation_id,'item_id':item_id,'lote_fornecedor':lot,'data_validade':expiry.isoformat() if expiry else None}
    return _record(organization_code=context.organization_code,material_id=item.material_id,kind='entrada',
                   quantity=Decimal(line['quantity_base']),value=Decimal(conversion['converted_amount']),policy=policy,
                   request=request,snapshot={'valuation_id':valuation_id,'item':line['item'],'conversion':conversion,
                     'lote_fornecedor':lot,'data_validade':request['data_validade']},actor=actor,key=key,commit=commit,
                   item_id=item.id,unit_id=item.material_unidade_id)
