"""Preço original e câmbio explícitos congelados antes do recebimento físico."""
import json
from decimal import Decimal, localcontext
from math import isfinite
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from core.db import db
from services.core.organization_service import Result
from .financial_stock_contract import preview_conversion, text, decimal_text
from addons.addon_estoque.root.model.organization_stock import OrderValuation, OrganizationMovement
from addons.addon_estoque.root.model.item_pedido_compra import ItemPedidoCompra
from .purchase_context_service import document, get_context
from .organization_stock_service import dump, canonical


def legacy_decimal(value):
    """Adaptador explícito dos campos Float persistidos; não recupera precisão perdida."""
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value):
        raise ValueError('Quantidade, fator ou preço persistido inválido.')
    return Decimal(decimal_text(format(Decimal(str(value)), 'f')))


def item_signature(item):
    from .purchase_pricing_service import exact_line
    exact = exact_line('order', item)
    if exact:
        return {'id':item.id,'material_id':exact['material_id'],'material_unidade_id':exact['material_unidade_id'],
                'quantidade':exact['quantity'],'fator':exact['factor'],'preco_unitario':exact['unit_price'],
                'unidade_original':exact['unit']}
    quantity=legacy_decimal(item.quantidade)
    factor=legacy_decimal(item.fator_conversao_aplicado)
    price=legacy_decimal(item.preco_unitario)
    if quantity <= 0 or factor <= 0 or price < 0:
        raise ValueError('Quantidade/fator positivos e preço não negativo são obrigatórios.')
    return {'id':item.id,'material_id':item.material_id,'material_unidade_id':item.material_unidade_id,
            'quantidade':canonical(quantity),'fator':canonical(factor),'preco_unitario':canonical(price),
            'unidade_original':item.material_unidade.unidade if item.material_unidade else None}


def build_snapshot(order_id, data, *, reserve=False):
    required={'source_currency','operation_date','rate_id'}
    if not isinstance(data,dict) or set(data) not in (required, required | {'policy_version_id'}):
        raise ValueError('Informe moeda original, data e taxa (null na moeda-base); versão é opcional e explícita.')
    order=document('order',order_id,reserve=reserve)
    context=get_context('order',order.id)
    if context is None:
        raise ValueError('Pedido sem vínculo organizacional explícito.')
    from .purchase_pricing_service import get_pricing
    pricing = get_pricing('order', order.id)
    if pricing and data['source_currency'] != pricing.currency_code:
        raise ValueError('Moeda original deve coincidir com o cadastro monetário do pedido.')
    if order.status != 'confirmado':
        raise ValueError('Avaliação monetária exige pedido confirmado, com itens congelados.')
    items=ItemPedidoCompra.query.filter_by(pedido_compra_id=order.id,is_deleted=False).order_by(ItemPedidoCompra.material_id,ItemPedidoCompra.id).populate_existing().all()
    if not items:
        raise ValueError('Pedido sem itens ativos.')
    lines=[]
    for item in items:
        original=item_signature(item)
        with localcontext() as ctx:
            ctx.prec=64
            base=Decimal(original['quantidade'])*Decimal(original['fator'])
            total=Decimal(original['quantidade'])*Decimal(original['preco_unitario'])
        decimal_text(canonical(base),positive=True)
        conversion=preview_conversion({'organization_code':context.organization_code,'source_currency':data['source_currency'],
            'amount':canonical(total),'operation_date':data['operation_date'],'rate_id':data['rate_id'],
            'policy_version_id':data.get('policy_version_id')})
        lines.append({'item':original,'quantity_base':canonical(base),'conversion':conversion,
                      'material_name':item.material.nome,'unit_base':item.material.unidade_medida})
    freight = json.loads(pricing.snapshot_json)['freight'] if pricing else canonical(legacy_decimal(order.valor_frete or 0))
    return {'order_id':order.id,'organization_code':context.organization_code,'supplier_id':order.fornecedor_id,
            'freight_excluded':True,'freight_original':freight, 'items':lines}


def prepare_valuation(order_id, data, *, actor):
    try:
        actor=text(actor,120,'Autor')
        order=document('order',order_id,reserve=True)
        required={'source_currency','operation_date','rate_id'}
        if not isinstance(data,dict) or set(data) not in (required,required | {'policy_version_id'}):
            raise ValueError('Dados de avaliação inválidos.')
        request=dump(data | {'policy_version_id':data.get('policy_version_id')})
        existing=OrderValuation.query.filter_by(order_id=order.id).populate_existing().first()
        if existing:
            same=existing.request_json == request
            result=existing.to_dict() if same else None
            db.session.rollback()
            return Result(same,data=result,error=None if same else 'Avaliação já congelada com parâmetros diferentes.',code=200 if same else 409)
        snapshot=build_snapshot(order_id,data)
        row=OrderValuation(order_id=order.id,request_json=request,snapshot_json=dump(snapshot),created_by=actor)
        db.session.add(row);db.session.commit()
        return Result(True,data=row.to_dict(),code=201)
    except ValueError as exc:
        db.session.rollback()
        return Result(False,error=str(exc),code=422)
    except SQLAlchemyError:
        db.session.rollback()
        return Result(False,error='Conflito ao congelar avaliação; nenhuma alteração confirmada.',code=409)


def receive(order, *, actor, dados_por_item=None):
    """Reserva do pedido obtida pelo chamador; um commit para todos os itens."""
    from . import estoque_service
    if order.status != 'confirmado':
        raise estoque_service.PedidoCompraStatusInvalidoError('Recebimento organizacional exige pedido confirmado.')
    plan=OrderValuation.query.filter_by(order_id=order.id).populate_existing().first()
    if plan is None:
        raise ValueError('Congele a avaliação monetária antes de receber; saldos e custos por organização exigem moeda e conversão explícitas.')
    frozen=json.loads(plan.snapshot_json)
    items=ItemPedidoCompra.query.filter_by(pedido_compra_id=order.id,is_deleted=False).order_by(ItemPedidoCompra.material_id,ItemPedidoCompra.id).populate_existing().all()
    if {item.id for item in items} != {line['item']['id'] for line in frozen['items']}:
        raise ValueError('Itens do pedido divergem da avaliação congelada.')
    if OrganizationMovement.query.join(ItemPedidoCompra,OrganizationMovement.pedido_compra_item_id == ItemPedidoCompra.id).filter(ItemPedidoCompra.pedido_compra_id == order.id).first():
        raise ValueError('Pedido já possui recebimento organizacional registrado.')
    extras=dados_por_item or {}
    if not isinstance(extras,dict) or set(extras) - {item.id for item in items}:
        raise ValueError('Dados de lote/validade devem pertencer aos itens deste pedido.')
    if any(not isinstance(extra,dict) for extra in extras.values()):
        raise ValueError('Dados por item inválidos.')
    movements=[]
    if db.session.info.get('organization_receipt_order') is not None:
        raise ValueError('Recebimento organizacional já em andamento nesta transação.')
    db.session.info['organization_receipt_order']=order.id
    try:
        for item in items:
            line=next(line for line in frozen['items'] if line['item']['id'] == item.id)
            result=estoque_service.registrar_movimentacao(item.material_id,'entrada',line['quantity_base'],
                organization_code=frozen['organization_code'],valuation_id=plan.id,pedido_compra_item_id=item.id,
                actor=actor,lote_fornecedor=extras.get(item.id,{}).get('lote_fornecedor'),
                data_validade=extras.get(item.id,{}).get('data_validade'),commit=False)
            movements.append(result['movimentacao'])
    finally:
        db.session.info.pop('organization_receipt_order',None)
    order.status='recebido';order.updated_at=datetime.now(timezone.utc)
    db.session.commit()
    return {'pedido_compra':order.to_dict(),'movimentacoes':movements,'organization_code':frozen['organization_code']}
