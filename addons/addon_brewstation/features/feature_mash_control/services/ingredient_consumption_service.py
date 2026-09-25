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
from math import isfinite

from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_estoque.root.services import estoque_service, material_lookup
from addons.addon_brewstation.features.feature_envase.services.unidade_conversao import converter_quantidade


class LoteNaoEncontradoError(Exception):
    pass


class ReceitaNaoVinculadaError(Exception):
    pass


class IngredientesPendentesError(ValueError):
    pass


def conferir_ingredientes(recipe_id: int) -> dict:
    """Prévia sem efeitos colaterais para a confirmação e a tela do lote."""
    itens = []
    for ing in RecipeIngredient.query.filter_by(recipe_id=recipe_id, is_deleted=False).order_by(RecipeIngredient.id).all():
        linha = {"id": ing.id, "descricao": ing.descricao_origem,
                 "material_id": ing.material_id, "quantidade": ing.quantidade,
                 "unidade": ing.unidade_medida, "estado": "pronto", "motivo": None,
                 "quantidade_base": None, "unidade_base": None, "custo_estimado": None}
        if ing.status_resolucao == "ignorado":
            linha["estado"] = "ignorado"
            linha["motivo"] = "Excluído do consumo por decisão registrada na receita."
        elif not ing.material_id or ing.status_resolucao != "resolvido":
            linha["estado"] = "pendente"
            linha["motivo"] = "Vincule um material ou marque Não consumir do estoque."
        elif ing.quantidade is None or not isfinite(ing.quantidade) or ing.quantidade <= 0:
            linha["estado"] = "pendente"
            linha["motivo"] = "Informe uma quantidade positiva para consumo."
        else:
            try:
                linha["quantidade_base"], linha["unidade_base"] = _quantidade_base(ing)
            except ValueError as exc:
                linha["estado"] = "pendente"
                linha["motivo"] = str(exc)
            else:
                saldo = material_lookup.get_saldo(ing.material_id)
                custo = saldo.get("custo_medio") if saldo else None
                if custo is not None:
                    linha["custo_estimado"] = linha["quantidade_base"] * custo
        itens.append(linha)
    return {"itens": itens, "pendencias": [i for i in itens if i["estado"] == "pendente"],
            "prontos": [i for i in itens if i["estado"] == "pronto"],
            "ignorados": [i for i in itens if i["estado"] == "ignorado"]}


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
    if not isfinite(quantidade) or quantidade <= 0:
        raise ValueError(f"Quantidade convertida inválida no ingrediente {ing.descricao_origem}")
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
        if ing.status_resolucao == "ignorado":
            continue
        if ing.status_resolucao != "resolvido":
            avisos.append(f"{ing.descricao_origem}: vínculo pendente")
            if not ing.material_id:
                sem_material_vinculado.append(ing.descricao_origem)
            continue
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


def confirmar_consumo_ingredientes(brew_session_id: int, *, commit: bool = True) -> dict:
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

    conferencia = conferir_ingredientes(lote.recipe_id)
    if conferencia["pendencias"]:
        nomes = ", ".join(f"{linha['descricao']} ({linha['motivo']})"
                          for linha in conferencia["pendencias"][:3])
        raise IngredientesPendentesError(
            f"Resolva {len(conferencia['pendencias'])} ingrediente(s) antes de confirmar: {nomes}."
        )
    preparados = [(db.session.get(RecipeIngredient, linha["id"]), linha["quantidade_base"])
                 for linha in conferencia["prontos"]]
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
        if commit:
            db.session.commit()
        else:
            db.session.flush()
    except Exception:
        db.session.rollback()
        raise

    return {
        "ja_confirmado": False,
        "resultados": resultados,
        "custo_total_insumos": custo_total,
        "confirmacao_completa": True,
    }
