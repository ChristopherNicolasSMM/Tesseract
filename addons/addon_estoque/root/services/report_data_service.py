"""DTO público de saldos v1. Manual: não é sobrescrito pelo CrudGen.

Reports recebe somente este JSON; não conhece modelos de Estoque.
Leitura própria, limitada, sem commit/rollback da sessão do consumidor.
"""
from decimal import Decimal
from flask import abort
from flask_login import current_user
from core.db import db
from ..model.material import Material
from ..model.saldo import Saldo


def _decimal(value):
    return None if value is None else str(Decimal(str(value)))


def build_stock_report_data(material_id=None):
    """Retorna valores registrados (strings decimais), sem refazer custos.

    Mais de 2000 saldos exige filtro/paginação em uma futura versão; nunca
    retorna uma lista truncada como se fosse o estoque completo.
    """
    # has_permission pode consultar banco; não provocar autoflush de negócio.
    with db.session.no_autoflush:
        if not current_user.is_authenticated:
            abort(401)
        if not all(current_user.has_permission(p) for p in ('saldos.list', 'materials.list')):
            abort(403)
    if material_id is not None and (type(material_id) is not int or material_id < 1):
        abort(400)
    with db.session.session_factory() as reader:
        query = (reader.query(Saldo, Material).join(Material, Saldo.material_id == Material.id)
                 .filter(Saldo.is_deleted.is_(False), Material.is_deleted.is_(False)))
        if material_id is not None:
            query = query.filter(Material.id == material_id)
        rows = query.order_by(Material.nome, Material.id).limit(2001).all()
        if material_id is not None and not rows:
            abort(404)
        if len(rows) > 2000:
            abort(413)
        items = [{
            'material_id': material.id, 'nome': material.nome, 'sku': material.sku,
            'quantidade_atual': _decimal(saldo.quantidade_atual),
            'custo_medio': _decimal(saldo.custo_medio),
            'valor_total_estoque': _decimal(saldo.valor_total_estoque),
            'estoque_minimo': _decimal(saldo.estoque_minimo),
            'estoque_maximo': _decimal(saldo.estoque_maximo),
            'status': saldo.status,
            'ultima_atualizacao': saldo.ultima_atualizacao.isoformat() if saldo.ultima_atualizacao else None,
        } for saldo, material in rows]
    return {'contract': 'estoque.saldos.v1', 'items': items}


def generate_stock_report(template_key, *, material_id=None, version=None, parameters=None, format='html'):
    """Integração opcional: requer Reports ativo e template já publicado."""
    data = build_stock_report_data(material_id)
    from addons.addon_reports.root.services.report_template_service import generate_report
    return generate_report(template_key, version=version, data=data, parameters=parameters, format=format)


def build_organization_stock_report_data(organization_code, material_id=None):
    """DTO de leitura organizacional; não mistura nem atualiza Saldo legado."""
    from services.core.organization_service import resolve_organization_by_code
    from ..model.organization_stock import OrganizationBalance
    with db.session.no_autoflush:
        if not current_user.is_authenticated:
            abort(401)
        if not all(current_user.has_permission(p) for p in ('saldos.list', 'materials.list')):
            abort(403)
        if type(organization_code) is not str or not organization_code:
            abort(400)
        if material_id is not None and (type(material_id) is not int or material_id < 1):
            abort(400)
        try:
            org = resolve_organization_by_code(organization_code, require_active=False)
        except ValueError:
            abort(404)
    with db.session.session_factory() as reader:
        query = reader.query(OrganizationBalance, Material).join(Material, OrganizationBalance.material_id == Material.id).filter(
            OrganizationBalance.organization_code == org['code'], Material.is_deleted.is_(False))
        if material_id is not None:
            query = query.filter(Material.id == material_id)
        rows = query.order_by(Material.nome, Material.id).limit(2001).all()
        if len(rows) > 2000:
            abort(413)
        items = [balance.to_dict() | {'nome':material.nome,'sku':material.sku,'unidade':material.unidade_medida}
                 for balance,material in rows]
    return {'contract':'estoque.organizacao.saldos.v1','organization':{'code':org['code'],'name':org['name'],'is_active':org['is_active']},'items':items}
