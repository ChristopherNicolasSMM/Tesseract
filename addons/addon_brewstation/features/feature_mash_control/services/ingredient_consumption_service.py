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


def calcular_custo_insumos_receita(recipe_id: int) -> dict:
    """
    Preview de custo dos insumos de uma receita — soma
    `quantidade × Saldo.custo_medio` de cada RecipeIngredient
    resolvido. Não grava nada, pode ser chamada quantas vezes o
    usuário quiser (inclusive antes de a receita ter uma BrewSession).

    `custo_medio` já vem por unidade-base (skill 23, Fase 2 —
    MaterialUnidade.fator_para_base já normalizou na entrada) — não
    precisa de conversão nenhuma aqui.
    """
    ingredientes = RecipeIngredient.query.filter_by(recipe_id=recipe_id, is_deleted=False).all()
    detalhes = []
    total = 0.0
    sem_material_vinculado = []

    for ing in ingredientes:
        if not ing.material_id or not ing.quantidade:
            if not ing.material_id:
                sem_material_vinculado.append(ing.descricao_origem)
            continue
        saldo = material_lookup.get_saldo(ing.material_id)
        custo_medio = saldo.get("custo_medio") if saldo else None
        custo_linha = (ing.quantidade * custo_medio) if custo_medio is not None else None
        if custo_linha is not None:
            total += custo_linha
        detalhes.append({
            "recipe_ingredient_id": ing.id,
            "material_id": ing.material_id,
            "descricao_origem": ing.descricao_origem,
            "quantidade": ing.quantidade,
            "custo_medio": custo_medio,
            "custo_linha": custo_linha,
        })

    return {
        "custo_total_estimado": total,
        "detalhes": detalhes,
        "ingredientes_sem_material_vinculado": sem_material_vinculado,
    }


def confirmar_consumo_ingredientes(brew_session_id: int) -> dict:
    """
    Baixa real de estoque dos insumos da receita vinculada ao lote —
    idempotente via `BrewSession.insumos_baixados_em` (chamar de novo
    num lote já confirmado só devolve o resultado já congelado, não
    baixa de novo).

    Best-effort por linha (mesmo padrão de
    `estoque_service.movimentar_estoque_em_massa` — cada
    `registrar_movimentacao` já comita a própria transação, forçar
    atomicidade entre N ingredientes exigiria reescrevê-la). Falha
    numa linha não impede as demais; o lote é marcado como confirmado
    de qualquer forma ao final, com o detalhe de sucesso/erro por
    linha no retorno — mesma UX já usada nos outros fluxos em massa do
    projeto.
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

    resultados = []
    custo_total = 0.0
    for ing in _ingredientes_com_material(lote.recipe_id):
        saldo = material_lookup.get_saldo(ing.material_id)
        custo_medio = saldo.get("custo_medio") if saldo else None
        try:
            resultado = estoque_service.registrar_movimentacao(
                ing.material_id, "saida", ing.quantidade,
                custo_unitario=custo_medio,
                observacoes=f"Consumo de insumo — confirmação de ingredientes do lote #{lote.id} ({lote.name}).",
            )
            custo_linha = resultado["movimentacao"].get("custo_total")
            if custo_linha is not None:
                custo_total += custo_linha
            resultados.append({
                "recipe_ingredient_id": ing.id, "material_id": ing.material_id,
                "sucesso": True, "custo_total": custo_linha,
            })
        except Exception as e:  # noqa: BLE001
            resultados.append({
                "recipe_ingredient_id": ing.id, "material_id": ing.material_id,
                "sucesso": False, "erro": str(e),
            })

    lote.insumos_baixados_em = datetime.now(timezone.utc)
    lote.custo_total_insumos = custo_total
    db.session.commit()

    return {
        "ja_confirmado": False,
        "resultados": resultados,
        "custo_total_insumos": custo_total,
    }
