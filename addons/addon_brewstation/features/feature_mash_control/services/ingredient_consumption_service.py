"""
addons/addon_brewstation/features/feature_mash_control/services/ingredient_consumption_service.py

Skill 26 (docs/skills/26-proposta-envase-consumo-insumo-custo-industrializacao.md,
seção 2) — não é gerado pelo CrudGen, mesmo papel de
ingredient_resolution_service.py/envase_estoque_service.py.

Duas funções com papéis diferentes desde o desenho (não uma opção ou
outra, ver seção 2.4 da skill):

- `calcular_custo_insumos_receita()` — PURA, não grava nada. Pode
  rodar quantas vezes o usuário quiser antes de decidir brassar.
- `confirmar_consumo_ingredientes()` — baixa real de estoque, só roda
  uma vez por lote (protegida por `BrewSession.insumos_baixados_em`).
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_estoque.root.services import estoque_service, material_lookup
from addons.addon_brewstation.features.feature_envase.services.unidade_conversao import converter_quantidade


class LoteNaoEncontradoError(Exception):
    pass


class ReceitaNaoVinculadaError(Exception):
    pass


def _ingredientes_com_material(recipe_id: int) -> list[RecipeIngredient]:
    """Só os que têm material_id resolvido e quantidade preenchida —
    linhas sem material vinculado (ex.: água, ainda pendente de
    de-para) são informativas, não erro, e ficam de fora do cálculo/
    consumo por definição, não por falha."""
    todos = RecipeIngredient.query.filter_by(recipe_id=recipe_id, is_deleted=False).all()
    return [i for i in todos if i.material_id and i.quantidade]


def _quantidade_base(ing: RecipeIngredient) -> tuple[float, str | None]:
    """Converte a unidade da receita para a mesma base usada pelo Saldo."""
    base = material_lookup.get_unidade_base(ing.material_id)
    material = material_lookup.get_material(ing.material_id)
    if material is None:
        raise ValueError(f"Material #{ing.material_id} não está disponível")
    unidade_base = base["unidade"] if base else material.get("unidade_medida")
    if ing.unidade_medida and not unidade_base:
        raise ValueError(f"Material #{ing.material_id} não tem unidade-base cadastrada")
    quantidade, confiavel = converter_quantidade(
        ing.quantidade, ing.unidade_medida, unidade_base, ing.material_id,
    )
    if not confiavel:
        raise ValueError(
            f"Não foi possível converter {ing.unidade_medida} para {unidade_base} "
            f"no ingrediente {ing.descricao_origem}"
        )
    return quantidade, unidade_base


def calcular_custo_insumos_receita(recipe_id: int) -> dict:
    """
    Preview de custo dos insumos de uma receita — soma
    `quantidade × Saldo.custo_medio` de cada RecipeIngredient
    resolvido. Não grava nada, pode ser chamada quantas vezes o
    usuário quiser (inclusive antes de a receita ter uma BrewSession).

    Converte a quantidade da receita para a unidade-base antes de
    multiplicar pelo custo médio e comparar com o saldo.
    """
    ingredientes = RecipeIngredient.query.filter_by(recipe_id=recipe_id, is_deleted=False).all()
    detalhes = []
    total = 0.0
    sem_material_vinculado = []
    avisos = []

    for ing in ingredientes:
        if not ing.material_id or not ing.quantidade:
            if not ing.material_id:
                sem_material_vinculado.append(ing.descricao_origem)
            continue
        try:
            quantidade_base, unidade_base = _quantidade_base(ing)
        except ValueError as exc:
            avisos.append(str(exc))
            continue
        saldo = material_lookup.get_saldo(ing.material_id)
        custo_medio = saldo.get("custo_medio") if saldo else None
        disponivel = saldo.get("quantidade_atual", 0) if saldo else 0
        custo_linha = (quantidade_base * custo_medio) if custo_medio is not None else None
        if custo_medio is None:
            avisos.append(f"{ing.descricao_origem}: sem custo médio")
        if custo_linha is not None:
            total += custo_linha
        detalhes.append({
            "recipe_ingredient_id": ing.id,
            "material_id": ing.material_id,
            "descricao_origem": ing.descricao_origem,
            "quantidade": ing.quantidade,
            "unidade_medida": ing.unidade_medida,
            "quantidade_base": quantidade_base,
            "unidade_base": unidade_base,
            "saldo_disponivel": disponivel,
            "quantidade_faltante": max(0, quantidade_base - disponivel),
            "custo_medio": custo_medio,
            "custo_linha": custo_linha,
        })

    return {
        "custo_total_estimado": total,
        "detalhes": detalhes,
        "ingredientes_sem_material_vinculado": sem_material_vinculado,
        "avisos": avisos,
        "custo_completo": not avisos and not sem_material_vinculado,
    }


def confirmar_consumo_ingredientes(brew_session_id: int) -> dict:
    """
    Baixa real de estoque dos insumos da receita vinculada ao lote —
    idempotente via `BrewSession.insumos_baixados_em` (chamar de novo
    num lote já confirmado só devolve o resultado já congelado, não
    baixa de novo).

    Todas as saídas e a marcação do lote são confirmadas juntas.
    Qualquer falha desfaz as saídas, permitindo tentar novamente.
    """
    lote = BrewSession.query.filter_by(id=brew_session_id, is_deleted=False).first()
    if lote is None:
        raise LoteNaoEncontradoError(f"BrewSession id={brew_session_id} não encontrada ou removida")

    if lote.insumos_baixados_em is not None:
        return {
            "ja_confirmado": True,
            "insumos_baixados_em": lote.insumos_baixados_em.isoformat(),
            "custo_total_insumos": lote.custo_total_insumos,
        }

    if not lote.recipe_id:
        raise ReceitaNaoVinculadaError(f"BrewSession id={brew_session_id} não tem receita vinculada")

    ingredientes = _ingredientes_com_material(lote.recipe_id)
    preparados = [(ing, _quantidade_base(ing)[0]) for ing in ingredientes]
    resultados = []
    custo_total = 0.0
    try:
        for ing, quantidade_base in preparados:
            saldo = material_lookup.get_saldo(ing.material_id)
            custo_medio = saldo.get("custo_medio") if saldo else None
            resultado = estoque_service.registrar_movimentacao(
                ing.material_id, "saida", quantidade_base,
                custo_unitario=custo_medio,
                observacoes=f"Consumo de insumo — confirmação de ingredientes do lote #{lote.id} ({lote.name}).",
                commit=False,
            )
            custo_linha = resultado["movimentacao"].get("custo_total")
            if custo_linha is not None:
                custo_total += custo_linha
            resultados.append({
                "recipe_ingredient_id": ing.id, "material_id": ing.material_id,
                "sucesso": True, "custo_total": custo_linha,
            })
        lote.insumos_baixados_em = datetime.now(timezone.utc)
        lote.custo_total_insumos = custo_total
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return {
        "ja_confirmado": False,
        "resultados": resultados,
        "custo_total_insumos": custo_total,
        "confirmacao_completa": True,
    }
