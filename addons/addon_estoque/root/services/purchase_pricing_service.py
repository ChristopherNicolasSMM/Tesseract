"""Decimais recebidos como texto, moeda declarada e herança sem reconversão."""
import json
from decimal import Decimal, localcontext
from sqlalchemy import select, update, inspect
from sqlalchemy.exc import SQLAlchemyError
from core.db import db
from services.core.organization_service import Result, resolve_organization_by_code
from addons.addon_estoque.root.model.purchase_pricing import PurchasePricing
from addons.addon_estoque.root.model.pedido_compra import PedidoCompra
from addons.addon_estoque.root.model.cotacao import Cotacao
from addons.addon_estoque.root.model.item_pedido_compra import ItemPedidoCompra
from addons.addon_estoque.root.model.item_cotacao import ItemCotacao
from addons.addon_estoque.root.model.item_processo_cotacao import ItemProcessoCotacao
from addons.addon_estoque.root.model.processo_cotacao import ProcessoCotacao
from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
from addons.addon_estoque.root.model.organization_stock import OrderValuation
from .purchase_context_service import document, get_context
from .financial_stock_contract import decimal_text, text, stock_valuation_options
from .organization_stock_service import canonical, dump


def get_pricing(kind, ident):
    if kind not in ('order', 'quotation') or type(ident) is not int or ident <= 0:
        raise ValueError('Documento monetário inválido.')
    field = PurchasePricing.order_id if kind == 'order' else PurchasePricing.quotation_id
    with db.session.no_autoflush:
        return PurchasePricing.query.filter(field == ident).populate_existing().first()


def pricing_document(kind, ident, *, reserve=False):
    if kind == 'order':
        return document('order', ident, reserve=reserve)
    if kind != 'quotation' or type(ident) is not int or ident <= 0:
        raise ValueError('Documento monetário inválido.')
    with db.session.no_autoflush:
        quote = db.session.get(Cotacao, ident)
        if quote is None:
            raise ValueError('Cotação ausente.')
        document('process', quote.processo_cotacao_id, reserve=reserve)
        quote = Cotacao.query.filter_by(id=ident).populate_existing().first()
    if quote is None or quote.is_deleted:
        raise ValueError('Cotação ausente ou removida.')
    return quote


def active_items(kind, ident):
    cls = ItemPedidoCompra if kind == 'order' else ItemCotacao
    field = cls.pedido_compra_id if kind == 'order' else cls.cotacao_id
    return cls.query.filter(field == ident, cls.is_deleted.is_(False)).order_by(cls.id).populate_existing().all()


def exact_number(value, *, positive=False):
    return canonical(Decimal(decimal_text(value, positive=positive)))


def _legacy_factor(value):
    from .order_valuation_service import legacy_decimal
    return canonical(legacy_decimal(value))


def freeze(kind, ident, data, *, actor, commit=True, inherited=None):
    """Imutável depois de explícita confirmação, inclusive ainda em rascunho.

    inherited é interno à geração atômica; referencia a resposta já congelada.
    Não há importação de dados Float como se fossem preços exatos.
    """
    try:
        if not isinstance(data, dict) or set(data) != {'currency_code', 'freight', 'items'}:
            raise ValueError('Informe currency_code, freight e todos os items (id, quantity, unit_price).')
        actor = text(actor, 120, 'Autor')
        obj = pricing_document(kind, ident, reserve=True)
        existing = get_pricing(kind, ident)
        if existing:
            # Comparar apenas os dados originais; históricos continuam legíveis/repetíveis.
            frozen = json.loads(existing.snapshot_json)
            original = {'currency_code': existing.currency_code, 'freight': frozen['freight'],
                        'items': [{k: line[k] for k in ('id', 'quantity', 'unit_price')} for line in frozen['items']]}
            normalized = normalize(data)
            same = normalized == original
            result = existing.to_dict() if same else None
            if commit:
                db.session.rollback()
            return Result(same, data=result, error=None if same else 'Cadastro já congelado com valores diferentes.', code=200 if same else 409)
        data = normalize(data)
        context = get_context('order' if kind == 'order' else 'process',
                              ident if kind == 'order' else obj.processo_cotacao_id)
        if context is None:
            raise ValueError('Vincule a organização antes do cadastro monetário.')
        resolve_organization_by_code(context.organization_code)
        options = stock_valuation_options(context.organization_code)
        if data['currency_code'] not in {c['code'] for c in options['currencies']}:
            raise ValueError('Selecione uma moeda cadastrada no Financeiro.')
        if kind == 'order':
            if obj.status != 'rascunho' or OrderValuation.query.filter_by(order_id=ident).first():
                raise ValueError('Cadastro monetário exige pedido rascunho sem avaliação prévia.')
        else:
            process = document('process', obj.processo_cotacao_id)
            if obj.status not in ('rascunho', 'respondida') or process.status not in ('aberto', 'comparado'):
                raise ValueError('Cotação deve estar em rascunho/respondida, com processo aberto.')
            if data['freight'] != '0':
                raise ValueError('Frete da cotação ainda não possui contrato; informe zero.')
        items = active_items(kind, ident)
        if not items or {i.id for i in items} != {line['id'] for line in data['items']}:
            raise ValueError('Informe exatamente todos os itens ativos do documento, sem duplicatas.')
        lines = []
        for item in items:
            raw = next(line for line in data['items'] if line['id'] == item.id)
            if kind == 'quotation':
                parent = item.item_processo_cotacao
                if parent is None or parent.is_deleted or parent.processo_cotacao_id != obj.processo_cotacao_id:
                    raise ValueError('Item solicitado incompatível com o processo da cotação.')
                if item.pedido_compra_item_id or item.selecionado_como_vencedor:
                    raise ValueError('Congele o preço antes de escolher vencedores ou gerar pedidos.')
            material = item.material if kind == 'order' else item.item_processo_cotacao.material
            if material is None or material.is_deleted:
                raise ValueError('Material ausente.')
            unit = db.session.get(MaterialUnidade, item.material_unidade_id)
            if unit is None or unit.is_deleted or unit.material_id != item.material_id:
                raise ValueError('Unidade inválida ou incompatível com o material.')
            source = None
            source_item_id = (inherited or {}).get(item.id)
            if source_item_id is not None:
                if commit or kind != 'order' or type(source_item_id) is not int:
                    raise ValueError('Herança monetária exige geração atômica de pedido.')
                source_item = db.session.get(ItemCotacao, source_item_id)
                source_pricing = get_pricing('quotation', source_item.cotacao_id) if source_item else None
                source = exact_line('quotation', source_item) if source_pricing else None
                if (source is None or source_item.pedido_compra_item_id != item.id
                    or source_pricing.organization_code != context.organization_code
                    or source_pricing.currency_code != data['currency_code']
                    or source['material_id'] != item.material_id
                    or source['material_unidade_id'] != item.material_unidade_id
                    or source['quantity'] != raw['quantity'] or source['unit_price'] != raw['unit_price']):
                    raise ValueError('Origem monetária incompatível com o item gerado.')
            factor = source['factor'] if source else _legacy_factor(item.fator_conversao_aplicado)
            factor = exact_number(factor, positive=True)
            with localcontext() as ctx:
                ctx.prec = 64
                base = exact_number(Decimal(raw['quantity']) * Decimal(factor), positive=True)
                subtotal = exact_number(Decimal(raw['quantity']) * Decimal(raw['unit_price']))
            line = raw | {'material_id': item.material_id, 'material_unidade_id': item.material_unidade_id,
                          'factor': factor, 'quantity_base': base, 'subtotal': subtotal,
                          'unit': source['unit'] if source else unit.unidade}
            if source:
                line.update(source_quotation_id=source_item.cotacao_id, source_quotation_item_id=source_item.id)
            if kind == 'quotation':
                line['requested_item_id'] = item.item_processo_cotacao_id
                item.quantidade_ofertada = float(raw['quantity'])
            else:
                item.quantidade = float(raw['quantity'])
            # Compatibilidade para telas antigas; a cadeia monetária lê somente strings acima.
            item.preco_unitario = float(raw['unit_price'])
            item.fator_conversao_aplicado = float(factor)
            item.quantidade_convertida_base = float(base)
            item.subtotal = float(subtotal)
            lines.append(line)
        if kind == 'order':
            obj.valor_frete = float(data['freight'])
        db.session.flush()
        snapshot = {'supplier_id': obj.fornecedor_id, 'freight': data['freight'], 'items': lines}
        row = PurchasePricing(organization_code=context.organization_code, currency_code=data['currency_code'],
                              created_by=actor, snapshot_json=dump(snapshot),
                              **{('order_id' if kind == 'order' else 'quotation_id'): ident})
        db.session.add(row)
        db.session.commit() if commit else db.session.flush()
        return Result(True, data=row.to_dict(), code=201)
    except ValueError as exc:
        db.session.rollback()
        return Result(False, error=str(exc), code=422)
    except SQLAlchemyError:
        db.session.rollback()
        return Result(False, error='Conflito no cadastro monetário; nenhuma alteração confirmada.', code=409)
    except Exception:
        db.session.rollback()
        raise


def normalize(data):
    if not isinstance(data['currency_code'], str):
        raise ValueError('Moeda inválida.')
    currency = data['currency_code']
    freight = exact_number(data['freight'])
    if Decimal(freight) < 0:
        raise ValueError('Frete não pode ser negativo.')
    if not isinstance(data['items'], list) or not data['items']:
        raise ValueError('Informe os itens.')
    lines = []
    for line in data['items']:
        if not isinstance(line, dict) or set(line) != {'id', 'quantity', 'unit_price'} or type(line['id']) is not int or line['id'] <= 0:
            raise ValueError('Cada item exige id inteiro, quantity e unit_price como texto decimal.')
        quantity = exact_number(line['quantity'], positive=True)
        price = exact_number(line['unit_price'])
        if Decimal(price) < 0:
            raise ValueError('Preço não pode ser negativo.')
        lines.append({'id': line['id'], 'quantity': quantity, 'unit_price': price})
    if len({line['id'] for line in lines}) != len(lines):
        raise ValueError('Itens duplicados.')
    return {'currency_code': currency, 'freight': freight, 'items': sorted(lines, key=lambda line: line['id'])}


def exact_line(kind, item):
    pricing = get_pricing(kind, item.pedido_compra_id if kind == 'order' else item.cotacao_id)
    if pricing is None:
        return None
    line = next((line for line in json.loads(pricing.snapshot_json)['items'] if line['id'] == item.id), None)
    if line is None:
        raise ValueError('Item ausente do cadastro monetário congelado; preserve o documento.')
    return line


def comparison(process_id):
    document('process', process_id)
    items = ItemCotacao.query.join(Cotacao).filter(Cotacao.processo_cotacao_id == process_id,
        Cotacao.is_deleted.is_(False), ItemCotacao.is_deleted.is_(False)).all()
    quotes = {item.cotacao_id: get_pricing('quotation', item.cotacao_id) for item in items}
    if not any(quotes.values()):
        return {'exact': False, 'items': []}
    if not all(quotes.values()):
        raise ValueError('Congele a moeda e os preços de todas as cotações respondidas antes de comparar.')
    currencies = {p.currency_code for p in quotes.values()}
    if len(currencies) != 1:
        raise ValueError('Moedas diferentes: comparação/seleção bloqueada até conversão explícita. Não existe paridade automática.')
    lines = []
    factors = {}
    for item in items:
        line = exact_line('quotation', item)
        if line is None:
            raise ValueError('Itens divergem do cadastro monetário.')
        factors.setdefault(line['requested_item_id'], set()).add(line['factor'])
        lines.append({'id': item.id, 'requested_item_id': line['requested_item_id'],
                      'material': item.item_processo_cotacao.material.nome,
                      'supplier': item.cotacao.fornecedor.razao_social,
                      'quantity': line['quantity'], 'unit_price': line['unit_price'], 'subtotal': line['subtotal'],
                      'selected': item.selecionado_como_vencedor, 'generated': bool(item.pedido_compra_item_id)})
    if any(len(values) > 1 for values in factors.values()):
        raise ValueError('Fatores de unidade diferentes para o mesmo item solicitado: comparação exige conversão explícita.')
    lines.sort(key=lambda line: (line['requested_item_id'], Decimal(line['unit_price']), line['id']))
    return {'exact': True, 'currency_code': next(iter(currencies)), 'items': lines}


def protect_priced_document(mapper, connection, target, *, deleting=False):
    """Guarda ORM e reserva do documento: inclusive escritores sem passar pela UI."""
    cls = type(target)
    if cls is PedidoCompra:
        owner, ident = PurchasePricing.order_id, target.id
        protected = ('fornecedor_id', 'valor_frete')
        lock_cls, lock_id = PedidoCompra, ident
    elif cls is Cotacao:
        owner, ident = PurchasePricing.quotation_id, target.id
        protected = ('fornecedor_id', 'processo_cotacao_id', 'is_deleted')
        lock_cls, lock_id = ProcessoCotacao, target.processo_cotacao_id
    elif cls is ItemPedidoCompra:
        owner, ident = PurchasePricing.order_id, target.pedido_compra_id
        protected = ('pedido_compra_id', 'material_id', 'material_unidade_id', 'quantidade', 'preco_unitario',
                     'fator_conversao_aplicado', 'quantidade_convertida_base', 'subtotal', 'is_deleted')
        lock_cls, lock_id = PedidoCompra, ident
    elif cls is ItemCotacao:
        owner, ident = PurchasePricing.quotation_id, target.cotacao_id
        protected = ('cotacao_id', 'item_processo_cotacao_id', 'quantidade_ofertada', 'preco_unitario',
                     'fator_conversao_aplicado', 'quantidade_convertida_base', 'subtotal', 'is_deleted')
        quote = connection.execute(select(Cotacao.processo_cotacao_id).where(Cotacao.id == ident)).scalar()
        lock_cls, lock_id = ProcessoCotacao, quote
    else:  # item solicitado: preservar material/unidade dos fornecedores que congelaram resposta
        lock_cls, lock_id = ProcessoCotacao, target.processo_cotacao_id
        owner = PurchasePricing.quotation_id
        ident = None
        protected = ('processo_cotacao_id', 'material_id', 'material_unidade_id', 'quantidade_desejada', 'is_deleted')
    state = inspect(target)
    ids = [ident]
    field = 'pedido_compra_id' if cls is ItemPedidoCompra else 'cotacao_id' if cls is ItemCotacao else None
    if field:
        ids += list(state.attrs[field].history.deleted)
    lock_ids = [lock_id]
    if cls is ItemCotacao:
        lock_ids = connection.execute(select(Cotacao.processo_cotacao_id).where(Cotacao.id.in_(ids))).scalars().all()
    elif cls is ItemPedidoCompra:
        lock_ids = ids
    elif cls in (Cotacao, ItemProcessoCotacao):
        lock_ids += list(state.attrs.processo_cotacao_id.history.deleted)
    # Origem e destino em ordem estável: transferência não pode atravessar
    # uma confirmação concorrente do documento original.
    for key in sorted({key for key in lock_ids if key is not None}):
        connection.execute(update(lock_cls).where(lock_cls.id == key).values(updated_at=lock_cls.updated_at))
    query = select(PurchasePricing.id).where(owner.in_(ids))
    if cls is ItemProcessoCotacao:
        query = select(PurchasePricing.id).join(ItemCotacao, ItemCotacao.cotacao_id == PurchasePricing.quotation_id).where(
            ItemCotacao.item_processo_cotacao_id == target.id)
    priced = connection.execute(query).first()
    if priced and (deleting or state.pending or any(state.attrs[field].history.has_changes() for field in protected)):
        raise ValueError('Documento possui cadastro monetário congelado; preserve os itens, moeda, fornecedor e frete.')


def protect_priced_delete(mapper, connection, target):
    protect_priced_document(mapper, connection, target, deleting=True)
