"""
addons/addon_brewstation/features/feature_envase/services/precificacao_service.py

Motor de cálculo (proposta-precificacao-envase.md) — fluxo simula ->
calcula -> cria Envase. Não depende de nenhum Envase existir ainda
(lê ingredientes via BrewSession.recipe_id); se um envase_id for
passado, soma também o custo de embalagem dos ItemEnvase dele.

Resolução de custo por Material (mesma regra pra ingrediente e
embalagem): 1) último preço real pago (ItemPedidoCompra, mais
recente); 2) se não achar E o Material for malte/lupulo/levedura
(feature_ingredientes), cai no preço padrão daquele tipo; 3) senão,
0.0 com origem_preco="sem_preco" — nunca esconde do usuário que o
custo está sem base real (decisão da conversa).
"""
from __future__ import annotations

from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_envase.model.envase import Envase
from addons.addon_brewstation.features.feature_envase.model.item_envase import ItemEnvase
from addons.addon_brewstation.features.feature_envase.model.calculo_precificacao import CalculoPrecificacao
from addons.addon_brewstation.features.feature_envase.model.item_custo_ingrediente import ItemCustoIngrediente
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


def _preco_real_mais_recente(material_id: int) -> float | None:
    """Último ItemPedidoCompra.preco_unitario registrado pro Material — None se nunca comprado."""
    from addons.addon_estoque.root.model.item_pedido_compra import ItemPedidoCompra
    from addons.addon_estoque.root.model.pedido_compra import PedidoCompra

    item = (
        ItemPedidoCompra.query
        .join(PedidoCompra, ItemPedidoCompra.pedido_compra_id == PedidoCompra.id)
        .filter(ItemPedidoCompra.material_id == material_id, ItemPedidoCompra.is_deleted.is_(False))
        .order_by(PedidoCompra.data_pedido.desc(), ItemPedidoCompra.id.desc())
        .first()
    )
    return item.preco_unitario if item else None


def _resolver_custo_material(material_id: int) -> tuple[float, str]:
    """Retorna (preco_unitario_usado, origem_preco)."""
    preco_real = _preco_real_mais_recente(material_id)
    if preco_real is not None:
        return preco_real, "real"

    tipo = _tipo_insumo_do_material(material_id)
    if tipo is not None:
        return get_valor_padrao(tipo), "padrao"

    return 0.0, "sem_preco"


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
    calculo = CalculoPrecificacao.query.get(calculo_id)
    if not calculo:
        return None
    calculo.envase_id = envase_id
    db.session.commit()
    return calculo.to_dict()


def _calcular(lote_id: int, envase_id: int | None, percentual_lucro: float,
              percentual_ipi: float, percentual_icms: float) -> dict:
    lote = BrewSession.query.get(lote_id)
    if not lote:
        raise ValueError("Lote (BrewSession) não encontrado.")

    itens_resultado = []
    custo_ingredientes_total = 0.0

    if lote.recipe_id:
        ingredientes = RecipeIngredient.query.filter_by(
            recipe_id=lote.recipe_id, is_deleted=False
        ).all()
        for ing in ingredientes:
            if not ing.material_id or not ing.quantidade:
                continue
            preco_unitario, origem = _resolver_custo_material(ing.material_id)
            custo_total = preco_unitario * ing.quantidade
            custo_ingredientes_total += custo_total
            itens_resultado.append({
                "material_id": ing.material_id,
                "quantidade": ing.quantidade,
                "preco_unitario_usado": preco_unitario,
                "custo_total": custo_total,
                "origem_preco": origem,
            })

    custo_embalagem_total = 0.0
    if envase_id:
        itens_envase = ItemEnvase.query.filter_by(envase_id=envase_id, is_deleted=False).all()
        for item in itens_envase:
            preco_unitario, origem = _resolver_custo_material(item.material_id)
            custo_total = preco_unitario * item.quantidade
            custo_embalagem_total += custo_total
            itens_resultado.append({
                "material_id": item.material_id,
                "quantidade": item.quantidade,
                "preco_unitario_usado": preco_unitario,
                "custo_total": custo_total,
                "origem_preco": origem,
            })

    subtotal = custo_ingredientes_total + custo_embalagem_total
    valor_lucro = subtotal * (percentual_lucro / 100.0)
    total_antes_impostos = subtotal + valor_lucro
    valor_ipi = total_antes_impostos * (percentual_ipi / 100.0)
    valor_icms = total_antes_impostos * (percentual_icms / 100.0)
    valor_total = total_antes_impostos + valor_ipi + valor_icms

    return {
        "lote_id": lote_id,
        "envase_id": envase_id,
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
