"""
addons/addon_brewstation/features/feature_envase/services/precificacao_service.py

Motor de cálculo (proposta-precificacao-envase.md) — fluxo simula ->
calcula -> cria Envase. Não depende de nenhum Envase existir ainda
(lê ingredientes via BrewSession.recipe_id); se um envase_id for
passado, usa o snapshot de embalagens; ItemEnvase é fallback estimado legado.
Depois da confirmação, usa o total de ingredientes congelado no lote, sem
recalcular preços ou fabricar detalhamento histórico por ingrediente.

Resolução de custo por Material (mesma regra pra ingrediente e
embalagem): 1) `Saldo.custo_medio` (já mantido pelo resto do
addon_estoque sempre em unidade-base do Material, skill 23 — não
ItemPedidoCompra direto, que é por unidade DE COMPRA, não de base);
2) se não achar E o Material for malte/lupulo/levedura
(feature_ingredientes), cai no preço padrão daquele tipo; 3) senão,
0.0 com origem_preco="sem_preco" — nunca esconde do usuário que o
custo está sem base real (decisão da conversa).

CORREÇÃO (achado do Christopher, print de tela): preço é sempre por
uma UNIDADE (unidade-base do Material pro real, `PrecoPadraoInsumo.
unidade` pro padrão) e a quantidade do RecipeIngredient vem na
unidade DA RECEITA (`unidade_medida`) — sem converter, lúpulo em
gramas era multiplicado direto por um preço por quilo (1000x mais
caro). `unidade_conversao.converter_quantidade()` resolve isso antes
de multiplicar.
"""
from __future__ import annotations

from math import isfinite

from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_envase.model.envase import Envase
from addons.addon_brewstation.features.feature_envase.model.item_envase import ItemEnvase
from addons.addon_brewstation.features.feature_envase.model.calculo_precificacao import CalculoPrecificacao
from addons.addon_brewstation.features.feature_envase.model.item_custo_ingrediente import ItemCustoIngrediente
from addons.addon_brewstation.features.feature_envase.services.unidade_conversao import converter_quantidade
from addons.addon_brewstation.features.feature_ingredientes.model.malte import Malte
from addons.addon_brewstation.features.feature_ingredientes.model.lupulo import Lupulo
from addons.addon_brewstation.features.feature_ingredientes.model.levedura import Levedura
from addons.addon_brewstation.features.feature_ingredientes.services.preco_padrao_lookup import get_valor_padrao


def _tipo_insumo_do_material(material_id: int) -> str | None:
    """malte/lupulo/levedura se o Material for um desses (1:1, feature_ingredientes) — senão None."""
    if Malte.query.filter_by(material_id=material_id).first():
        return "malte"
    if Lupulo.query.filter_by(material_id=material_id).first():
        return "lupulo"
    if Levedura.query.filter_by(material_id=material_id).first():
        return "levedura"
    return None


def _custo_real_por_base(material_id: int) -> float | None:
    """
    `Saldo.custo_medio` — já mantido pelo resto de addon_estoque sempre
    em unidade-base do Material (skill 23, `estoque_service.
    receber_pedido_compra`). None se o Material nunca teve entrada.
    """
    from addons.addon_estoque.root.services import material_lookup
    saldo = material_lookup.get_saldo(material_id)
    return saldo.get("custo_medio") if saldo and not saldo.get("is_deleted") else None


def _unidade_base_material(material_id: int) -> str | None:
    from addons.addon_estoque.root.services import material_lookup
    base = material_lookup.get_unidade_base(material_id)
    if base:
        return base["unidade"]
    material = material_lookup.get_material(material_id)
    return material.get("unidade_medida") if material else None


def _resolver_custo_material(material_id: int) -> tuple[float, str, str | None]:
    """Retorna (preco_unitario, origem_preco, unidade_do_preco)."""
    preco_real = _custo_real_por_base(material_id)
    if preco_real is not None:
        return preco_real, "real", _unidade_base_material(material_id)

    tipo = _tipo_insumo_do_material(material_id)
    if tipo is not None:
        from addons.addon_brewstation.features.feature_ingredientes.model.preco_padrao_insumo import (
            PrecoPadraoInsumo,
        )
        row = PrecoPadraoInsumo.query.filter_by(tipo_insumo=tipo).first()
        unidade_padrao = row.unidade if row else None
        return get_valor_padrao(tipo), "padrao", unidade_padrao

    return 0.0, "sem_preco", None


def simular(lote_id: int, envase_id: int | None, percentual_lucro: float,
            percentual_ipi: float, percentual_icms: float) -> dict:
    """
    Calcula sem gravar nada — usado pela etapa "simula" do fluxo
    simula -> calcula -> cria envase. Retorna o mesmo formato de
    `calcular_e_salvar`, só que sem `id` (nunca foi persistido).
    """
    resultado = _calcular(lote_id, envase_id, percentual_lucro, percentual_ipi, percentual_icms)
    return resultado


def calcular_e_salvar(lote_id: int, envase_id: int | None, percentual_lucro: float,
                       percentual_ipi: float, percentual_icms: float) -> dict:
    """Calcula e grava CalculoPrecificacao + ItemCustoIngrediente — envase_id pode ser None."""
    resultado = _calcular(lote_id, envase_id, percentual_lucro, percentual_ipi, percentual_icms)

    calculo = CalculoPrecificacao(
        lote_id=lote_id,
        envase_id=envase_id,
        custo_ingredientes_total=resultado["custo_ingredientes_total"],
        custo_embalagem_total=resultado["custo_embalagem_total"],
        subtotal=resultado["subtotal"],
        percentual_lucro=percentual_lucro,
        valor_lucro=resultado["valor_lucro"],
        percentual_ipi=percentual_ipi,
        valor_ipi=resultado["valor_ipi"],
        percentual_icms=percentual_icms,
        valor_icms=resultado["valor_icms"],
        valor_total=resultado["valor_total"],
        base_calculo_snapshot=resultado["base_calculo_snapshot"],
    )
    db.session.add(calculo)
    db.session.flush()  # precisa do id pra gravar os itens

    for item in resultado["itens"]:
        db.session.add(ItemCustoIngrediente(
            calculo_id=calculo.id,
            material_id=item["material_id"],
            quantidade=item["quantidade"],
            preco_unitario_usado=item["preco_unitario_usado"],
            custo_total=item["custo_total"],
            origem_preco=item["origem_preco"],
        ))

    db.session.commit()

    resultado["id"] = calculo.id
    return resultado


def vincular_envase(calculo_id: int, envase_id: int) -> dict | None:
    """Preenche envase_id de um cálculo já salvo — etapa 'cria envase' do fluxo, depois de decidido."""
    calculo = db.session.get(CalculoPrecificacao, calculo_id)
    if not calculo:
        return None
    lote = db.session.get(BrewSession, calculo.lote_id)
    if lote is None or lote.is_deleted:
        raise ValueError("Lote (BrewSession) não encontrado.")
    envase = db.session.get(Envase, envase_id)
    if envase is None or envase.is_deleted or envase.lote_id != calculo.lote_id:
        raise ValueError("Envase deste lote não encontrado.")
    if envase.status != "registrado":
        raise ValueError("Envase cancelado não pode ser vinculado à precificação.")
    if calculo.envase_id is not None and calculo.envase_id != envase_id:
        raise ValueError("Este cálculo já está vinculado a outro envase.")
    calculo.envase_id = envase_id
    db.session.commit()
    return calculo.to_dict()


def _material_display(material_id: int) -> str:
    from addons.addon_estoque.root.services.material_lookup import get_material

    resolvido = get_material(material_id)
    return resolvido["display"] if resolvido else f"Material #{material_id}"


def _calcular(lote_id: int, envase_id: int | None, percentual_lucro: float,
              percentual_ipi: float, percentual_icms: float) -> dict:
    for value in (percentual_lucro, percentual_ipi, percentual_icms):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
            raise ValueError("Percentuais devem ser números finitos e não negativos.")
    lote = db.session.get(BrewSession, lote_id)
    if not lote or lote.is_deleted:
        raise ValueError("Lote (BrewSession) não encontrado.")

    itens_resultado = []
    custo_ingredientes_total = 0.0
    estimativa_incompleta = False

    envase = None
    if envase_id is not None:
        envase = db.session.get(Envase, envase_id)
        if envase is None or envase.is_deleted or envase.lote_id != lote_id:
            raise ValueError("Envase deste lote não encontrado.")
        if envase.status != "registrado":
            raise ValueError("Envase cancelado não pode compor uma nova precificação.")

    from addons.addon_brewstation.features.feature_mash_control.services.production_organization_service import context
    if context(lote_id):
        return _organizational_price(lote, envase, percentual_lucro, percentual_ipi, percentual_icms)
    raise ValueError('Vincule uma organização ao lote para uma nova precificação; históricos salvos permanecem disponíveis.')

def _organizational_price(lote, envase, profit, ipi, icms):
    """Decimal autoritativo no snapshot; Float somente no DTO/colunas de apresentação legadas."""
    from decimal import Decimal, localcontext
    from addons.addon_brewstation.features.feature_mash_control.model.production_organization import ProductionConsumption
    from addons.addon_brewstation.features.feature_mash_control.services.production_organization_service import context
    from addons.addon_brewstation.features.feature_mash_control.services.organization_recipe_preview import preview
    link = context(lote.id).snapshot()
    consumed = db.session.get(ProductionConsumption, lote.id)
    frozen = consumed.snapshot() if consumed else None
    plan = None if frozen else preview(lote.recipe_id, link['organization_code'])
    with localcontext() as ctx:
        ctx.prec = 64
        ingredient_total = Decimal(frozen['custo_total_insumos'] if frozen else plan['custo_total_estimado'])
        ingredient = ingredient_total
        packaging = Decimal(0)
        units = volume = None
        if envase:
            production = envase.producao_snapshot
            if not production or production.get('version') != 2:
                raise ValueError('Envase sem custo organizacional congelado.')
            ingredient = Decimal(production['custo_cerveja'])
            packaging = Decimal(production['custo_embalagens'])
            units = Decimal(production['unidades_exatas'])
            volume = Decimal(production['litros_exatos'])
        subtotal = ingredient + packaging
        gain = subtotal * Decimal(str(profit)) / 100
        base = subtotal + gain
        tax_ipi = base * Decimal(str(ipi)) / 100
        tax_icms = base * Decimal(str(icms)) / 100
        total = base + tax_ipi + tax_icms
        amounts = {'custo_ingredientes_total': ingredient, 'custo_embalagem_total': packaging,
            'subtotal': subtotal, 'valor_lucro': gain, 'valor_ipi': tax_ipi, 'valor_icms': tax_icms, 'valor_total': total}
        if any(not value.is_finite() or abs(value) >= Decimal('1e18') for value in amounts.values()):
            raise ValueError('Resultado monetário fora da magnitude suportada.')
        exact = {key: format(value, 'f') for key, value in amounts.items()}
        incomplete = not frozen and not plan['custo_completo']
        basis = {'version': 2, 'organization_code': link['organization_code'], 'currency_code': link['policy']['currency_code'],
            'exact_amounts': exact, 'custo_ingredientes_lote_total': format(ingredient_total, 'f'),
            'origem_unidades': 'registrado' if envase else 'indisponivel',
            'escopo': 'envase' if envase else 'lote', 'ingredientes_registrados': frozen is not None,
            'embalagens_registradas': envase is not None, 'estimativa_incompleta': incomplete,
            'volume_envase_litros': float(volume) if volume else None,
            'unidades_envase': float(units) if units else None,
            'custo_por_unidade': float(subtotal / units) if units else None,
            'preco_por_unidade': float(total / units) if units else None,
            'preco_por_litro': float(total / volume) if volume else None}
    return {**{key: float(value) for key, value in amounts.items()},
        'base_calculo_snapshot': basis, 'organization_code': link['organization_code'],
        'currency_code': link['policy']['currency_code'], 'lote_id': lote.id, 'envase_id': envase.id if envase else None,
        'estimativa_incompleta': incomplete, 'ingredientes_registrados': frozen is not None,
        'embalagens_registradas': envase is not None, 'escopo_custo': 'Custos da organização e rateio congelado do envase.',
        'percentual_lucro': profit, 'percentual_ipi': ipi, 'percentual_icms': icms, 'itens': []}
