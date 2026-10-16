"""Vínculo explícito e baixa Decimal transacional por lote."""
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from sqlalchemy import update
from core.db import db
from services.core.organization_service import resolve_organization_by_code
from addons.addon_estoque.root.services.financial_stock_contract import resolve_selected_policy, text, day
from addons.addon_estoque.root.services.organization_stock_service import dump, canonical
from addons.addon_estoque.root.services import estoque_service
from ..model.brew_session import BrewSession
from ..model.production_organization import ProductionOrganization, ProductionConsumption


def reserve(session_id):
    if type(session_id) is not int or session_id <= 0:
        raise ValueError('Lote inválido.')
    db.session.execute(update(BrewSession).where(BrewSession.id == session_id).values(
        updated_at=BrewSession.updated_at).execution_options(synchronize_session=False))
    row = BrewSession.query.filter_by(id=session_id, is_deleted=False).populate_existing().first()
    if row is None:
        raise ValueError('Lote não encontrado ou removido.')
    return row


def context(session_id):
    return db.session.get(ProductionOrganization, session_id)


def bind(session_id, data, *, actor):
    try:
        if not isinstance(data, dict) or set(data) != {'organization_code', 'operation_date', 'policy_version_id'}:
            raise ValueError('Campos de vínculo produtivo inválidos.')
        actor = text(actor, 120, 'Autor')
        lote = reserve(session_id)
        org = resolve_organization_by_code(data['organization_code'])
        date = day(data['operation_date']).isoformat()
        policy = resolve_selected_policy(org['code'], policy_version_id=data['policy_version_id'], operation_date=date)
        request = {**data, 'organization_code': org['code']}
        previous = context(session_id)
        if previous:
            result = previous.snapshot()
            if result['request'] != request:
                raise ValueError('Lote já vinculado com outros dados.')
            db.session.rollback()
            return result
        from addons.addon_brewstation.features.feature_envase.model.envase import Envase
        if lote.insumos_baixados_em is not None or Envase.query.filter_by(lote_id=session_id).first():
            raise ValueError('Lote histórico com consumo/envase não pode ser reatribuído.')
        if lote.recipe_id is None:
            raise ValueError('Associe uma receita ao lote antes do vínculo.')
        frozen = {'request': request, 'recipe_id': lote.recipe_id, 'organization_code': org['code'],
                  'organization_name': org['name'], 'policy': policy, 'operation_date': date}
        db.session.add(ProductionOrganization(session_id=session_id, organization_code=org['code'],
            snapshot_json=dump(frozen), created_by=actor))
        db.session.commit()
        return frozen
    except Exception:
        db.session.rollback()
        raise


def consume(session_id, *, actor, commit=True):
    try:
        actor = text(actor, 120, 'Autor')
        lote = reserve(session_id)
        link = context(session_id)
        if link is None:
            raise ValueError('Vincule uma organização ao lote antes de consumir ou envasar.')
        previous = db.session.get(ProductionConsumption, session_id)
        if previous:
            return {**previous.snapshot(), 'ja_confirmado': True}
        frozen = link.snapshot()
        resolve_organization_by_code(link.organization_code)
        if lote.insumos_baixados_em is not None or lote.recipe_id != frozen['recipe_id']:
            raise ValueError('Receita/consumo diverge do vínculo organizacional do lote.')
        from .organization_recipe_preview import preview
        plan = preview(lote.recipe_id, link.organization_code)
        if plan['pendencias']:
            raise ValueError('Resolva os ingredientes pendentes antes de confirmar.')
        results = []
        with localcontext() as ctx:
            ctx.prec = 64
            total = Decimal(0)
            for line in plan['detalhes']:
                movement = estoque_service.registrar_movimentacao(line['material_id'], 'saida', line['quantidade'],
                    organization_code=link.organization_code, operation_date=frozen['operation_date'],
                    policy_version_id=frozen['request']['policy_version_id'],
                    idempotency_key=f'production:{session_id}:material:{line["material_id"]}',
                    observacoes=f'Consumo do lote #{session_id}', actor=actor, commit=False)
                cost = -Decimal(movement['movimentacao']['custo_total'])
                total += cost
                results.append({**line, 'sucesso': True, 'custo_total': canonical(cost),
                                'movimentacao_id': movement['movimentacao']['id']})
        snapshot = {'organization_code': link.organization_code, 'currency_code': frozen['policy']['currency_code'],
            'policy': frozen['policy'], 'resultados': results, 'custo_total_insumos': canonical(total),
            'confirmacao_completa': True, 'ja_confirmado': False}
        db.session.add(ProductionConsumption(session_id=session_id, snapshot_json=dump(snapshot)))
        lote.insumos_baixados_em = datetime.now(timezone.utc)
        lote.custo_total_insumos = float(total)  # compatibilidade visual; cálculo usa snapshot exato
        db.session.commit() if commit else db.session.flush()
        return snapshot
    except Exception:
        db.session.rollback()
        raise
