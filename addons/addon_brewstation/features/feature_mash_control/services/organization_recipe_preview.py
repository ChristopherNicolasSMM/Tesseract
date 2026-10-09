"""Prévia organizacional pura; não vincula receita/lote nem confirma consumo."""
from decimal import Decimal, localcontext

from core.db import db
from services.core.organization_service import resolve_organization_by_code
from addons.addon_financeiro.root.services.monetary_service import resolve_policy
from addons.addon_estoque.root.services.estoque_service import consultar_saldo
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.services.ingredient_consumption_service import conferir_ingredientes


def preview(recipe_id, organization_code):
    if isinstance(recipe_id, bool) or not isinstance(recipe_id, int) or recipe_id <= 0:
        raise ValueError('Receita inválida.')
    with db.session.no_autoflush, localcontext() as ctx:
        ctx.prec = 64
        recipe = db.session.get(MashRecipe, recipe_id)
        if recipe is None or recipe.is_deleted:
            raise ValueError('Receita não encontrada ou removida.')
        org = resolve_organization_by_code(organization_code)
        policy = resolve_policy(org['code'])
        conference = conferir_ingredientes(recipe_id, estimate_cost=False)
        grouped = {}
        for line in conference['prontos']:
            item = grouped.setdefault(line['material_id'], {
                'material_id': line['material_id'], 'unidade_base': line['unidade_base'],
                'descricao': line['descricao'],
                'ingredient_ids': [], 'quantidade': Decimal(0)})
            item['ingredient_ids'].append(line['id'])
            # Quantidades/conversões da receita ainda são Float no cadastro legado.
            # Adaptar a representação decimal disponível, sem prometer precisão perdida.
            item['quantidade'] += Decimal(str(line['quantidade_base']))
        total = Decimal(0)
        details, warnings = [], [line['motivo'] for line in conference['pendencias']]
        for material_id in sorted(grouped):
            item = grouped[material_id]
            balance = consultar_saldo(material_id, organization_code=org['code'])
            quantity = Decimal(balance['quantidade_atual']) if balance else Decimal(0)
            value = Decimal(balance['valor_total_estoque']) if balance else Decimal(0)
            if balance and balance['currency_code'] != policy['currency_code']:
                raise ValueError('Moeda do saldo incompatível com a política da organização.')
            missing = max(Decimal(0), item['quantidade'] - quantity)
            cost = value / quantity if quantity else None
            estimated = item['quantidade'] * value / quantity if quantity else None
            if estimated is not None:
                total += estimated
            else:
                warnings.append(f'Material #{material_id}: sem saldo para estimar custo.')
            if missing:
                warnings.append(f'Material #{material_id}: saldo insuficiente na organização {org["code"]}.')
            details.append({**item, 'quantidade': format(item['quantidade'], 'f'),
                'saldo_disponivel': format(quantity, 'f'), 'quantidade_faltante': format(missing, 'f'),
                'custo_medio': format(cost, 'f') if cost is not None else None,
                'custo_estimado': format(estimated, 'f') if estimated is not None else None})
        return {'recipe_id': recipe_id, 'organization_code': org['code'],
            'organization_name': org['name'], 'currency_code': policy['currency_code'],
            'detalhes': details, 'pendencias': conference['pendencias'],
            'ignorados': conference['ignorados'], 'avisos': warnings,
            'custo_total_estimado': format(total, 'f'),
            'custo_completo': not conference['pendencias'] and all(d['custo_estimado'] is not None for d in details),
            'estoque_suficiente': not warnings}
