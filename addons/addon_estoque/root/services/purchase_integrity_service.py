"""Contratos manuais de compras; overrides web/API e reserva transacional."""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
import logging

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, OperationalError
from core.db import db
from addons.addon_estoque.root.model.pedido_compra import PedidoCompra
from addons.addon_estoque.root.model.item_pedido_compra import ItemPedidoCompra
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
from addons.addon_estoque.root.model.fornecedor import Fornecedor
from addons.addon_estoque.root.model.transportadora import Transportadora
from addons.addon_estoque.root.model.movimentacao import Movimentacao
from addons.addon_estoque.root.model.item_cotacao import ItemCotacao

logger = logging.getLogger(__name__)


@dataclass
class Result:
    success: bool
    data: object = None
    error: str | None = None
    code: int = 200


class PurchaseRuleError(ValueError):
    def __init__(self, message, code=422):
        super().__init__(message)
        self.code = code


def reserve_order(ident):
    """UPDATE sem efeito semântico: reserva escritor SQLite/linha PostgreSQL.

    Releitura elimina dados antigos do identity map. A reserva permanece até
    commit/rollback da operação externa; nunca cria commit intermediário.
    """
    with db.session.no_autoflush:
        db.session.execute(update(PedidoCompra).where(PedidoCompra.id == ident).values(
            updated_at=PedidoCompra.updated_at).execution_options(synchronize_session=False))
        return PedidoCompra.query.filter_by(id=ident).populate_existing().first()


def _reference(cls, ident, label):
    if not isinstance(ident, int) or isinstance(ident, bool) or ident <= 0:
        raise PurchaseRuleError(f'{label}: selecione uma referência válida.')
    obj = cls.query.filter_by(id=ident).populate_existing().first()
    if obj is None or obj.is_deleted:
        raise PurchaseRuleError(f'{label}: referência ausente ou na lixeira.')
    return obj


def _finite(value, label, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise PurchaseRuleError(f'{label} deve ser um número finito.')
    if (positive and value <= 0) or (not positive and value < 0):
        raise PurchaseRuleError(f'{label} deve ser positivo.' if positive else f'{label} não pode ser negativo.')


def _validate_order(obj):
    _reference(Fornecedor, obj.fornecedor_id, 'Fornecedor')
    if obj.transportadora_id is not None:
        _reference(Transportadora, obj.transportadora_id, 'Transportadora')
    from datetime import date
    if not isinstance(obj.data_pedido, date):
        raise PurchaseRuleError('Data do pedido inválida.')
    if obj.valor_frete is not None:
        _finite(obj.valor_frete, 'Frete')
    if obj.status not in ('rascunho', 'enviado', 'confirmado', 'recebido', 'cancelado'):
        raise PurchaseRuleError('Status do pedido inválido.')


def _snapshot_item(obj, before):
    _reference(Material, obj.material_id, 'Material')
    unit = _reference(MaterialUnidade, obj.material_unidade_id, 'Unidade de compra')
    if unit.material_id != obj.material_id:
        raise PurchaseRuleError('A unidade de compra deve pertencer ao material do item.')
    _finite(obj.quantidade, 'Quantidade', positive=True)
    _finite(obj.preco_unitario, 'Preço unitário')
    # Só uma troca explícita de material/unidade em rascunho toma outro fator.
    # Salvar preço/quantidade ou reenvio do mesmo formulário preserva a conversão.
    changed = before is None or any(getattr(obj, f) != before[f]
                                    for f in ('material_id', 'material_unidade_id'))
    if changed:
        _finite(unit.fator_para_base, 'Fator de conversão', positive=True)
        obj.fator_conversao_aplicado = unit.fator_para_base
    elif obj.fator_conversao_aplicado is None:
        # Legado sem snapshot não recebe fator atual por edição administrativa.
        if any(getattr(obj, f) != before[f] for f in ('quantidade', 'preco_unitario')):
            raise PurchaseRuleError('Item legado sem fator: selecione explicitamente outra unidade válida ou crie novo item em rascunho.')
        return
    _finite(obj.fator_conversao_aplicado, 'Fator de conversão', positive=True)
    obj.quantidade_convertida_base = obj.quantidade * obj.fator_conversao_aplicado
    obj.subtotal = obj.quantidade * obj.preco_unitario
    _finite(obj.quantidade_convertida_base, 'Quantidade convertida', positive=True)
    _finite(obj.subtotal, 'Subtotal')


def _refs(kind, obj, *, active_only=False):
    if kind == 'order':
        query = ItemPedidoCompra.query.filter_by(pedido_compra_id=obj.id)
        if active_only:
            query = query.filter_by(is_deleted=False)
        return query.first() is not None
    return (Movimentacao.query.filter_by(pedido_compra_item_id=obj.id).first() is not None
            or ItemCotacao.query.filter_by(pedido_compra_item_id=obj.id).first() is not None)


def _has_receipt(kind, obj):
    query = Movimentacao.query
    if kind == 'order':
        query = query.join(ItemPedidoCompra, Movimentacao.pedido_compra_item_id == ItemPedidoCompra.id)
        return query.filter(ItemPedidoCompra.pedido_compra_id == obj.id).first() is not None
    return query.filter_by(pedido_compra_item_id=obj.id).first() is not None


def operate(kind, action, ident=None, data=None):
    """Mesmos contratos para services CRUD, formulários e APIs."""
    cls = PedidoCompra if kind == 'order' else ItemPedidoCompra
    try:
        if action == 'create':
            obj = cls()
            before = None
        else:
            obj = db.session.get(cls, ident)
            if obj is None:
                raise PurchaseRuleError('Registro não encontrado.', 404)
            if kind == 'order':
                obj = reserve_order(ident)
            else:
                parent = reserve_order(obj.pedido_compra_id)
                obj = cls.query.filter_by(id=ident).populate_existing().first()
                if obj is None:
                    raise PurchaseRuleError('Registro não encontrado.', 404)
            before = {c.name: getattr(obj, c.name) for c in cls.__table__.columns}

        if action in ('create', 'update'):
            if action == 'update' and obj.is_deleted:
                raise PurchaseRuleError('Não é possível editar um registro na lixeira.', 400)
            if not isinstance(data, dict):
                raise PurchaseRuleError('Dados inválidos.')
            if kind == 'order':
                from .pedido_compra_service import PedidoCompraService
                service = PedidoCompraService()
            else:
                from .item_pedido_compra_service import ItemPedidoCompraService
                service = ItemPedidoCompraService()
            fields = {k: v for k, v in data.items() if k in cls.__table__.columns}
            numeric = ('pedido_compra_id', 'material_id', 'material_unidade_id', 'quantidade',
                       'preco_unitario', 'fornecedor_id', 'transportadora_id', 'valor_frete')
            if any(isinstance(fields.get(f), bool) for f in numeric):
                raise PurchaseRuleError('Valores booleanos não são quantidades, preços ou identificadores válidos.')
            with db.session.no_autoflush:
                service._apply_fields(obj, fields)
                if kind == 'order':
                    obj.status = obj.status or 'rascunho'
                    _validate_order(obj)
                    if before is None and obj.status != 'rascunho':
                        raise PurchaseRuleError('Novo pedido deve começar como rascunho.', 409)
                    if obj.status == 'recebido' and (before is None or before['status'] != 'recebido'):
                        raise PurchaseRuleError('Use Registrar Entrada de Mercadoria para receber o pedido.', 409)
                    if before:
                        old = before['status']
                        transitions = {'rascunho': {'rascunho', 'enviado', 'confirmado', 'cancelado'},
                                       'enviado': {'enviado', 'confirmado', 'cancelado'},
                                       'confirmado': {'confirmado', 'cancelado'},
                                       'cancelado': {'cancelado'}, 'recebido': {'recebido'}}
                        if obj.status not in transitions.get(old, set()):
                            raise PurchaseRuleError('Transição de status não permitida. Preserve o pedido e crie outro rascunho.', 409)
                        protected = ('fornecedor_id', 'transportadora_id', 'data_pedido',
                                     'data_previsao_entrega', 'condicao_pagamento', 'valor_frete', 'numero')
                        has_receipt = _has_receipt(kind, obj)
                        if has_receipt and obj.status != old:
                            raise PurchaseRuleError('Pedido possui recebimento registrado; preserve seu status.', 409)
                        if (old != 'rascunho' or has_receipt) and any(getattr(obj, f) != before[f] for f in protected):
                            raise PurchaseRuleError('Dados do pedido estão congelados após envio/confirmação; somente observações e transições permitidas podem mudar.', 409)
                else:
                    if before and obj.pedido_compra_id != before['pedido_compra_id']:
                        raise PurchaseRuleError('O item não pode ser transferido para outro pedido.', 409)
                    parent = reserve_order(obj.pedido_compra_id)
                    if parent is None or parent.is_deleted:
                        raise PurchaseRuleError('Pedido ausente ou na lixeira.')
                    if parent.status != 'rascunho':
                        raise PurchaseRuleError('Itens só podem ser criados ou editados em pedido rascunho.', 409)
                    if _has_receipt('order', parent):
                        raise PurchaseRuleError('Pedido possui recebimento registrado; preserve os itens.', 409)
                    _snapshot_item(obj, before)
            if action == 'create':
                db.session.add(obj)
        else:
            if kind == 'item':
                if parent is None or parent.is_deleted or parent.status not in ('rascunho', 'cancelado'):
                    raise PurchaseRuleError('Manutenção de itens exige pedido rascunho ou cancelado ativo.', 409)
                if _refs(kind, obj):
                    raise PurchaseRuleError('Item possui referência histórica; preserve o registro.', 409)
            elif obj.status not in ('rascunho', 'cancelado') or _has_receipt(kind, obj):
                raise PurchaseRuleError('Preserve pedidos enviados, confirmados ou recebidos.', 409)
            if action == 'trash':
                if obj.is_deleted:
                    raise PurchaseRuleError('Já está na lixeira.', 400)
                if kind == 'order' and _refs(kind, obj, active_only=True):
                    raise PurchaseRuleError('Arquive os itens antes do pedido.', 409)
                obj.is_deleted, obj.deleted_at = True, datetime.now(timezone.utc)
            elif action == 'restore':
                if not obj.is_deleted:
                    raise PurchaseRuleError('Não está na lixeira.', 400)
                if kind == 'order':
                    _validate_order(obj)
                else:
                    _reference(Material, obj.material_id, 'Material')
                    unit = _reference(MaterialUnidade, obj.material_unidade_id, 'Unidade de compra')
                    if unit.material_id != obj.material_id:
                        raise PurchaseRuleError('Unidade incompatível com o material.')
                obj.is_deleted, obj.deleted_at = False, None
            elif action == 'delete_permanent':
                if not obj.is_deleted:
                    raise PurchaseRuleError('Apenas registros na lixeira podem ser excluídos permanentemente.', 400)
                if _refs(kind, obj):
                    raise PurchaseRuleError('Existem referências históricas; preserve o registro.', 409)
                db.session.delete(obj)
            else:
                raise PurchaseRuleError('Operação inválida.')
        db.session.commit()
        return Result(True, data={'id': ident} if action == 'delete_permanent' else obj,
                      code=201 if action == 'create' else 200)
    except PurchaseRuleError as exc:
        db.session.rollback()
        return Result(False, error=str(exc), code=exc.code)
    except (ValueError, TypeError, IntegrityError):
        db.session.rollback()
        return Result(False, error='Dados inválidos ou conflito com registro relacionado. Nenhuma alteração foi confirmada.', code=422)
    except OperationalError:
        db.session.rollback()
        return Result(False, error='Operação concorrente ou banco indisponível. Atualize e tente novamente.', code=409)
    except Exception:
        db.session.rollback()
        logger.exception('Falha de compras %s/%s', kind, action)
        return Result(False, error='Não foi possível salvar. Nenhuma alteração foi confirmada.', code=422)
