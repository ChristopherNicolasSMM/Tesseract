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

    ingredientes_registrados = lote.insumos_baixados_em is not None
    if ingredientes_registrados:
        if lote.custo_total_insumos is None:
            raise ValueError("Lote confirmado sem custo registrado: requer conferência do histórico.")
        custo_ingredientes_total = lote.custo_total_insumos
    elif lote.recipe_id:
        ingredientes = RecipeIngredient.query.filter_by(
            recipe_id=lote.recipe_id, is_deleted=False
        ).all()
        for ing in ingredientes:
            if ing.status_resolucao == "ignorado" or not ing.quantidade:
                continue
            if not ing.material_id:
                estimativa_incompleta = True
                continue
            preco_unitario, origem, unidade_preco = _resolver_custo_material(ing.material_id)
            quantidade_convertida, conversao_ok = converter_quantidade(
                ing.quantidade, ing.unidade_medida, unidade_preco, ing.material_id
            )
            estimativa_incompleta |= origem == "sem_preco" or not conversao_ok
            custo_total = preco_unitario * quantidade_convertida
            custo_ingredientes_total += custo_total
            itens_resultado.append({
                "material_id": ing.material_id,
                "material_nome": _material_display(ing.material_id),
                "quantidade": ing.quantidade,
                "unidade_medida": ing.unidade_medida,
                "quantidade_convertida": quantidade_convertida,
                "unidade_preco": unidade_preco,
                "conversao_confiavel": conversao_ok,
                "preco_unitario_usado": preco_unitario,
                "custo_total": custo_total,
                "origem_preco": origem,
            })

    custo_ingredientes_lote = custo_ingredientes_total
    basis = {"version": 1, "escopo": "lote", "fator_rateio": 1.0,
             "custo_ingredientes_lote_total": custo_ingredientes_lote,
             "volume_envase_litros": None, "volume_registrado_lote_litros": None,
             "volume_por_unidade_litros": None, "unidades_envase": None,
             "origem_unidades": "indisponivel"}
    if envase is not None:
        from addons.addon_brewstation.features.feature_envase.services.envase_cost_basis import volume_rateio, unit_basis
        basis.update(volume_rateio(envase))
        basis.update(unit_basis(envase))
        basis["escopo"] = "envase"
        custo_ingredientes_total *= basis["fator_rateio"]
        # Quantidades continuam sendo as quantidades da receita do lote.
        # Somente os custos das linhas são rateados; não inventa consumo parcial.
        for item in itens_resultado:
            item["custo_total_lote"] = item["custo_total"]
            item["custo_total"] *= basis["fator_rateio"]

    custo_embalagem_total = 0.0
    embalagens_registradas = envase is not None and envase.componentes_snapshot is not None
    if embalagens_registradas:
        for component in envase.componentes_snapshot:
            cost = component.get("custo_linha")
            if cost is None or component.get("custo_medio") is None:
                raise ValueError("Snapshot de embalagem sem custo registrado: requer conferência do histórico.")
            custo_embalagem_total += cost
            itens_resultado.append({
                "material_id": component["material_componente_id"],
                "material_nome": _material_display(component["material_componente_id"]),
                "quantidade": component["quantidade_total"],
                "unidade_medida": None, "quantidade_convertida": component["quantidade_total"],
                "unidade_preco": None, "conversao_confiavel": True,
                "preco_unitario_usado": component["custo_medio"],
                "custo_total": cost, "origem_preco": "registrado",
            })
    elif envase is not None:
        itens_envase = ItemEnvase.query.filter_by(envase_id=envase_id, is_deleted=False).all()
        if not itens_envase:
            estimativa_incompleta = True
        for item in itens_envase:
            preco_unitario, origem, unidade_preco = _resolver_custo_material(item.material_id)
            # ItemEnvase não guarda unidade própria — assume que já
            # está na unidade-base do Material (mesma premissa de
            # antes; sem dado de unidade de origem pra converter).
            estimativa_incompleta |= origem == "sem_preco"
            custo_total = preco_unitario * item.quantidade
            custo_embalagem_total += custo_total
            itens_resultado.append({
                "material_id": item.material_id,
                "material_nome": _material_display(item.material_id),
                "quantidade": item.quantidade,
                "unidade_medida": None,
                "quantidade_convertida": item.quantidade,
                "unidade_preco": unidade_preco,
                "conversao_confiavel": True,
                "preco_unitario_usado": preco_unitario,
                "custo_total": custo_total,
                "origem_preco": origem,
            })

    for cost in (custo_ingredientes_lote, custo_ingredientes_total, custo_embalagem_total):
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not isfinite(cost) or cost < 0:
            raise ValueError("Custos devem ser números finitos e não negativos; confira a base.")
    subtotal = custo_ingredientes_total + custo_embalagem_total
    valor_lucro = subtotal * (percentual_lucro / 100.0)
    total_antes_impostos = subtotal + valor_lucro
    valor_ipi = total_antes_impostos * (percentual_ipi / 100.0)
    valor_icms = total_antes_impostos * (percentual_icms / 100.0)
    valor_total = total_antes_impostos + valor_ipi + valor_icms

    if not all(isfinite(value) for value in (subtotal, valor_lucro, valor_ipi, valor_icms, valor_total)):
        raise ValueError("Resultado fora do intervalo numérico; confira os percentuais e custos.")
    units = basis["unidades_envase"]
    basis.update({"ingredientes_registrados": ingredientes_registrados,
                  "embalagens_registradas": embalagens_registradas,
                  "estimativa_incompleta": estimativa_incompleta,
                  "custo_por_unidade": subtotal / units if units else None,
                  "preco_por_unidade": valor_total / units if units else None,
                  "preco_por_litro": valor_total / basis["volume_envase_litros"] if envase else None})
    if any(value is not None and not isfinite(value) for value in
           (basis["custo_por_unidade"], basis["preco_por_unidade"], basis["preco_por_litro"])):
        raise ValueError("Preço unitário fora do intervalo numérico; confira o volume e as unidades.")
    return {
        "base_calculo_snapshot": basis,
        "lote_id": lote_id,
        "envase_id": envase_id,
        "estimativa_incompleta": estimativa_incompleta,
        "ingredientes_registrados": ingredientes_registrados,
        "embalagens_registradas": embalagens_registradas,
        "escopo_custo": ("Ingredientes rateados pelos litros registrados; embalagens deste envase." if envase else "Ingredientes do lote completo. Selecione um envase para rateio e preço por unidade."),
        "custo_ingredientes_total": custo_ingredientes_total,
        "custo_embalagem_total": custo_embalagem_total,
        "subtotal": subtotal,
        "percentual_lucro": percentual_lucro,
        "valor_lucro": valor_lucro,
        "percentual_ipi": percentual_ipi,
        "valor_ipi": valor_ipi,
        "percentual_icms": percentual_icms,
        "valor_icms": valor_icms,
        "valor_total": valor_total,
        "itens": itens_resultado,
    }
