"""Preparação organizacional de compras, sem reatribuir estoque legado."""
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from core.db import db
from services.core.organization_service import resolve_organization_by_code, Result
from addons.addon_estoque.root.model.purchase_context import PurchaseContext
from addons.addon_estoque.root.model.processo_cotacao import ProcessoCotacao
from addons.addon_estoque.root.model.pedido_compra import PedidoCompra
from addons.addon_estoque.root.model.cotacao import Cotacao
from addons.addon_estoque.root.model.item_cotacao import ItemCotacao
from addons.addon_estoque.root.model.item_pedido_compra import ItemPedidoCompra
from .purchase_integrity_service import reserve_order


def document(kind, ident, *, reserve=False):
    if kind not in ('process', 'order') or isinstance(ident, bool) or not isinstance(ident, int) or ident <= 0:
        raise ValueError('Documento de compra inválido.')
    model = PedidoCompra if kind == 'order' else ProcessoCotacao
    if reserve and kind == 'order':
        obj = reserve_order(ident)
    else:
        if reserve:
            with db.session.no_autoflush:
                db.session.execute(update(model).where(model.id == ident).values(updated_at=model.updated_at)
                                   .execution_options(synchronize_session=False))
        obj = model.query.filter_by(id=ident).populate_existing().first()
    if obj is None or obj.is_deleted:
        raise ValueError('Documento ausente ou removido.')
    return obj


def get_context(kind, ident):
    if kind not in ('process', 'order') or isinstance(ident, bool) or not isinstance(ident, int) or ident <= 0:
        raise ValueError('Documento de compra inválido.')
    field = PurchaseContext.order_id if kind == 'order' else PurchaseContext.process_id
    return PurchaseContext.query.filter(field == ident).populate_existing().first()


def bind_context(kind, ident, data, *, actor):
    try:
        if not isinstance(data, dict) or set(data) != {'organization_code'}:
            raise ValueError('Informe somente organization_code; nenhuma organização é inferida.')
        if not isinstance(actor, str) or not 1 <= len(actor.strip()) <= 120:
            raise ValueError('Autor inválido.')
        obj = document(kind, ident, reserve=True)
        org = resolve_organization_by_code(data['organization_code'], require_active=False)
        existing = get_context(kind, ident)
        if existing:
            same = existing.organization_code == org['code']
            db.session.rollback()  # libera a reserva inclusive em repetição idempotente
            return Result(same, data=existing.to_dict() if same else None,
                          error=None if same else 'Contexto organizacional já definido e imutável.', code=200 if same else 409)
        if not org['is_active']:
            raise ValueError('Organização inativa.')
        expected = ('rascunho',) if kind == 'order' else ('aberto', 'comparado')
        if obj.status not in expected:
            raise ValueError('Vincule a organização antes de enviar o pedido ou finalizar o processo.')
        if kind == 'process' and Cotacao.query.filter_by(processo_cotacao_id=ident).first():
            raise ValueError('Vincule a organização antes de convidar fornecedores; cotações existentes permanecem legadas.')
        if kind == 'order':
            linked = (ItemCotacao.query.join(ItemPedidoCompra, ItemCotacao.pedido_compra_item_id == ItemPedidoCompra.id)
                      .filter(ItemPedidoCompra.pedido_compra_id == ident).first())
        else:
            linked = (ItemCotacao.query.join(Cotacao, ItemCotacao.cotacao_id == Cotacao.id)
                      .filter(Cotacao.processo_cotacao_id == ident, ItemCotacao.pedido_compra_item_id.isnot(None)).first())
        if linked:
            raise ValueError('Documento com pedidos gerados: preserve a cadeia legada sem atribuição retroativa.')
        row = PurchaseContext(organization_code=org['code'], organization_name=org['name'], created_by=actor.strip(),
                              **{('order_id' if kind == 'order' else 'process_id'): ident})
        db.session.add(row)
        db.session.commit()
        return Result(True, data=row.to_dict(), code=201)
    except ValueError as exc:
        db.session.rollback()
        return Result(False, error=str(exc), code=422)
    except SQLAlchemyError:
        db.session.rollback()
        return Result(False, error='Conflito ao vincular documento; nenhuma alteração confirmada.', code=409)


def assert_global_operation_allowed(kind, ident):
    if get_context(kind, ident):
        raise ValueError('Compra vinculada a uma organização: operação bloqueada até a implantação de saldos e custos por organização.')
