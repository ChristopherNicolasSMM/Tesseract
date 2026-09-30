"""Saneamento local de ingredientes. Extensão manual, não gerada pelo CrudGen.

Não mantém o cache de-para compartilhado e não confirma consumo. Os futuros
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
    """Receita vinculada a sessão: requer revisão isolada, ainda não integrada."""


def _id_positivo(valor):
    return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0


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
