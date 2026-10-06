"""Saneamento local de ingredientes. Extensão manual, não gerada pelo CrudGen.

Não mantém o cache de-para compartilhado e não confirma consumo. Os
controllers devem validar autenticação, RBAC e contexto da planta antes de
chamar esta operação. Uma receita é global, não pertence a uma planta.
"""
from core.db import db
from addons.addon_estoque.root.services import material_lookup
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession


class IngredienteNaoEncontradoError(ValueError):
    """Receita/linha inexistente, apagada ou fora do contexto informado."""


class ReceitaEmUsoError(ValueError):
    """Receita vinculada a sessão: requer revisão isolada antes de editar."""


def _id_positivo(valor):
    return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0


def _editable_ingredient(recipe_id, ingredient_id):
    if not _id_positivo(recipe_id) or not _id_positivo(ingredient_id):
        raise IngredienteNaoEncontradoError("Ingrediente desta receita não encontrado.")
    receita = MashRecipe.query.filter_by(id=recipe_id, is_deleted=False).first()
    ingrediente = RecipeIngredient.query.filter_by(
        id=ingredient_id, recipe_id=recipe_id, is_deleted=False,
    ).first()
    if receita is None or ingrediente is None:
        raise IngredienteNaoEncontradoError("Ingrediente desta receita não encontrado.")

    # Sem filtro de lixeira: sessões removidas também possuem histórico.
    if BrewSession.query.filter_by(recipe_id=recipe_id).first() is not None:
        raise ReceitaEmUsoError(
            "Esta receita já está vinculada a uma sessão. Prepare uma revisão "
            "separada antes de alterar ingredientes; os lotes anteriores devem ser preservados."
        )
    return receita, ingrediente


def sanear_ingrediente(
    recipe_id: int,
    ingredient_id: int,
    *,
    status_resolucao: str,
    material_id: int | None = None,
    commit: bool = True,
) -> dict:
    """Altera apenas o vínculo/status de uma linha de uma receita sem sessões.

    `resolvido` exige Material disponível e ativo; `ignorado` exige material_id
    vazio e limpa o vínculo. Quantidade/unidade e especificações permanecem
    iguais: um vínculo válido ainda pode ter pendências na conferência.

    Qualquer sessão referenciando a receita, inclusive na lixeira, bloqueia a
    operação para preservar consumo futuro e consulta histórica. Não cria nova
    versão, não altera outras receitas e não reutiliza a propagação global de
    confirmar_mapeamento(). O chamador com commit=False confirma a transação;
    qualquer falha nesta operação faz rollback de toda a tentativa.
    """
    try:
        receita, ingrediente = _editable_ingredient(recipe_id, ingredient_id)

        if status_resolucao not in ("resolvido", "ignorado"):
            raise ValueError("Selecione um material ou Não consumir do estoque.")
        if status_resolucao == "resolvido":
            if not _id_positivo(material_id):
                raise ValueError("Selecione um Material de Estoque válido.")
            material = material_lookup.get_material(material_id)
            if material is None or not material.get("ativo", False):
                raise ValueError("O Material de Estoque não está disponível ou está inativo.")
        elif material_id is not None:
            raise ValueError("Não consumir do estoque deve ser enviado sem vínculo de material.")

        ingrediente.material_id = material_id
        ingrediente.status_resolucao = status_resolucao
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return ingrediente.to_dict()
    except Exception:
        db.session.rollback()
        raise


INGREDIENT_DATA_FIELDS = ("quantidade", "unidade_medida", "tempo_adicao_min", "etapa",
                          "uso_detalhado", "tipo_ingrediente", "cor_ebc", "rendimento",
                          "alpha_acidos", "atenuacao")


def editar_dados_ingrediente(recipe_id: int, ingredient_id: int, dados: dict, *,
                             usuario_id: int | None = None, commit: bool = True) -> dict:
    """Edita dados planejados, sincroniza alertas e registra snapshot juntos.

    Não muda vínculo/status, descrição de origem nem dados de sessões. Campos
    vazios permanecem pendentes quando necessários para consumo. Unidades são
    códigos do catálogo, sem inventar conversões. Valor legado fora do catálogo
    só pode ser preservado se não mudou, para permitir saneamento incremental.
    """
    from math import isfinite
    from addons.addon_estoque.root.services.unidade_catalogo_lookup import get_unidade
    from addons.addon_brewstation.features.feature_mash_control.model.recipe_history import RecipeHistory
    from addons.addon_brewstation.features.feature_mash_control.services.ingredient_resolution_service import build_recipe_snapshot
    from addons.addon_brewstation.features.feature_mash_control.services.recipe_timeline_service import sync_hop_alerts
    try:
        receita, ingrediente = _editable_ingredient(recipe_id, ingredient_id)
        if set(dados) - set(INGREDIENT_DATA_FIELDS):
            raise ValueError("A edição de dados recebeu campo não permitido.")
        clean = {}
        labels = {"quantidade": "Quantidade", "tempo_adicao_min": "Tempo de adição",
                  "cor_ebc": "Cor EBC", "rendimento": "Rendimento", "alpha_acidos": "Ácidos alfa",
                  "atenuacao": "Atenuação"}
        for field, raw in dados.items():
            value = str(raw).strip() if raw is not None else ""
            if field in labels:
                if isinstance(raw, bool):
                    raise ValueError(f"{labels[field]} deve ser um número válido.")
                if not value:
                    clean[field] = None
                    continue
                try:
                    number = float(value.replace(",", "."))
                except ValueError:
                    raise ValueError(f"{labels[field]} deve ser um número válido.") from None
                if not isfinite(number) or number < 0:
                    raise ValueError(f"{labels[field]} deve ser finito e não negativo.")
                if field == "tempo_adicao_min":
                    if not number.is_integer() or number > 2147483647:
                        raise ValueError("Tempo de adição deve ser um número inteiro de minutos válido.")
                    number = int(number)
                clean[field] = number
            elif field == "unidade_medida":
                if not value:
                    clean[field] = None
                else:
                    unit = get_unidade(value.upper())
                    if unit:
                        clean[field] = unit["codigo"]
                    elif value == ingrediente.unidade_medida:
                        clean[field] = value
                    else:
                        raise ValueError("Selecione uma unidade válida do catálogo.")
            elif field in ("etapa", "tipo_ingrediente"):
                options = ("mostura", "fervura", "fermentacao") if field == "etapa" else ("fermentavel", "lupulo", "levedura", "outro")
                if value and value not in options and value != getattr(ingrediente, field):
                    raise ValueError("Tipo ou etapa de ingrediente inválidos.")
                clean[field] = value or None
            else:
                if len(value) > 30:
                    raise ValueError("Uso detalhado deve ter até 30 caracteres.")
                clean[field] = value or None
        changed = any(getattr(ingrediente, field) != value for field, value in clean.items())
        if not changed:
            return ingrediente.to_dict()
        for field, value in clean.items():
            setattr(ingrediente, field, value)
        db.session.flush()
        sync_hop_alerts(receita, commit=False)
        history = RecipeHistory(recipe_id=recipe_id, alterado_por=usuario_id,
                                observacao=f"Dados planejados do ingrediente #{ingredient_id} editados no workspace.")
        history.set_snapshot(build_recipe_snapshot(receita))
        db.session.add(history)
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return ingrediente.to_dict()
    except Exception:
        db.session.rollback()
        raise


def ingredient_conversion_context(ingrediente):
    """Consulta pública de unidades; inclusive para receita já usada em lote."""
    from addons.addon_estoque.root.services.material_conversion_service import normalizar_unidade
    material = material_lookup.get_material(ingrediente.material_id)
    if not material or not material.get("ativo") or ingrediente.status_resolucao != "resolvido":
        return None
    base = material_lookup.get_unidade_base(ingrediente.material_id)
    origem = normalizar_unidade(ingrediente.unidade_medida)
    destino = normalizar_unidade(base["unidade"] if base else material.get("unidade_medida"))
    if not origem or not destino or origem == destino:
        return None
    from addons.addon_brewstation.features.feature_envase.services.unidade_conversao import converter_quantidade
    _, confiavel = converter_quantidade(1, origem, destino, ingrediente.material_id)
    return {"material_id": ingrediente.material_id, "material": material["display"],
            "origem": origem, "destino": destino, "necessita_conversao": not confiavel}


def configure_ingredient_conversion(recipe_id, ingredient_id, *, material_id_esperado,
                                    unidade_base_esperada, unidade_origem_esperada, fator):
    """Não edita receita/vínculo nem consumo; registra conversão no estoque."""
    from services.core.i18n_service import translate as t
    from addons.addon_estoque.root.services.material_conversion_service import cadastrar_conversao
    receita = MashRecipe.query.filter_by(id=recipe_id, is_deleted=False).first()
    ingrediente = RecipeIngredient.query.filter_by(id=ingredient_id, recipe_id=recipe_id, is_deleted=False).first()
    if receita is None or ingrediente is None:
        raise IngredienteNaoEncontradoError(t("brewstation_mashctrl.conversion.not_found"))
    context = ingredient_conversion_context(ingrediente)
    if context is None or context["material_id"] != material_id_esperado or context["origem"] != unidade_origem_esperada:
        raise ValueError(t("brewstation_mashctrl.conversion.stale_material"))
    return cadastrar_conversao(context["material_id"], context["origem"], fator,
                              unidade_base_esperada=unidade_base_esperada)
