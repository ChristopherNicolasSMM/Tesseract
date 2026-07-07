"""
addons/addon_brewstation/features/feature_brew_father/services/ingredient_autocreate_service.py

Orquestra o fluxo "Cadastrar todos automaticamente": para cada
RecipeIngredient pendente de resolucao (status_resolucao="pendente_depara"
com origem_receita="BrewFather"), cria Material em addon_estoque e, se
tipo_ingrediente for conhecido, cria a spec correspondente em
feature_ingredientes (Malte/Lupulo/Levedura) — depois chama
confirmar_mapeamento() para ligar tudo.

Reaproveitavel por futuras integracoes (feature_beersmith, etc.) —
mesmo principio de ingredient_resolution_service (nao duplicar logica).

RESOLUCAO DE CAMPOS OBRIGATORIOS (decisao desta sessao, ver BACKLOG.md):
Material agora exige sku/origem_id/tipo_produto_id/categoria_id, mas a
API do BrewFather nao fornece essa informacao. Resolvido assim:
- tipo_produto_id -> sempre o seed "Insumo" (nao e um "desconhecido"
  temporario - tudo que vem do sync de receita E insumo de fato).
- origem_id -> sempre o seed "A definir" (esse sim e desconhecido de
  verdade - BrewFather nao informa nacional/importado).
- categoria_id -> mantém o mesmo mapeamento tipo_ingrediente->categoria
  que já existia para o antigo campo string, agora resolvido para um
  registro real em Categoria (get_or_create, nome = valor antigo).
- sku -> "{TIPO_INGREDIENTE}-{10 primeiros caracteres do nome}",
  maiusculo, sem acento (ex.: "MALTE-PILSEN"), com sufixo numerico
  sequencial em caso de colisao (skill de unicidade do campo).
  {TIPO_INGREDIENTE} vem do tipo já existente em feature_ingredientes
  (MALTE/LUPULO/LEVEDURA), não de tipo_produto_id (que é sempre
  "Insumo" genérico). Editável depois pelo usuário.
- pendente_revisao=True sempre neste fluxo - só sinaliza na tela
  de-para, nunca bloqueia Movimentacao/Saldo (decisão explícita).
"""
from __future__ import annotations

import re
import unicodedata

from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.categoria import Categoria
from addons.addon_estoque.root.services.material_lookup import material_exists
from addons.addon_estoque.root.services.estoque_seed import (
    get_or_create_origem_a_definir,
    get_or_create_tipo_produto_insumo,
)
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.services.ingredient_resolution_service import confirmar_mapeamento


class AutoCadastroError(Exception):
    pass


# tipo_ingrediente (RecipeIngredient) -> prefixo de SKU. Fallback para
# tipos ainda não modelados (ex.: adjunto/agua_agente, backlog item 2c)
# usa um prefixo genérico em vez de quebrar a geração de SKU.
_TIPO_PARA_SKU_PREFIXO = {
    "fermentavel": "MALTE",
    "lupulo": "LUPULO",
    "levedura": "LEVEDURA",
}
_SKU_PREFIXO_FALLBACK = "INSUMO"


def _normalizar_para_sku(texto: str) -> str:
    """Maiusculo, sem acento, sem espaço - só [A-Z0-9]."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Z0-9]", "", sem_acento.upper())


def _gerar_sku(nome: str, tipo_ingrediente: str) -> str:
    prefixo = _TIPO_PARA_SKU_PREFIXO.get((tipo_ingrediente or "").lower(), _SKU_PREFIXO_FALLBACK)
    base = _normalizar_para_sku(nome)[:10] or "ITEM"
    sku = f"{prefixo}-{base}"

    if not Material.query.filter_by(sku=sku).first():
        return sku

    sufixo = 2
    while Material.query.filter_by(sku=f"{sku}-{sufixo}").first():
        sufixo += 1
    return f"{sku}-{sufixo}"


def _get_ou_criar_categoria(nome: str) -> Categoria:
    """Reaproveita por nome (unique) ou cria - substitui o antigo
    campo Material.categoria (string livre) por FK real (skill 02)."""
    existente = Categoria.query.filter_by(nome=nome, is_deleted=False).first()
    if existente:
        return existente
    nova = Categoria(nome=nome)
    db.session.add(nova)
    db.session.flush()
    return nova


def _get_ou_criar_material(nome: str, categoria: str, tipo_ingrediente: str) -> Material:
    """Retorna Material existente por nome (unique) ou cria um novo,
    resolvendo sku/origem_id/tipo_produto_id/categoria_id (ver
    docstring do módulo) e marcando pendente_revisao=True."""
    existente = Material.query.filter_by(nome=nome, is_deleted=False).first()
    if existente:
        return existente

    origem = get_or_create_origem_a_definir()
    tipo_produto = get_or_create_tipo_produto_insumo()
    categoria_obj = _get_ou_criar_categoria(categoria)
    sku = _gerar_sku(nome, tipo_ingrediente)

    novo = Material(
        nome=nome,
        sku=sku,
        origem_id=origem.id,
        tipo_produto_id=tipo_produto.id,
        categoria_id=categoria_obj.id,
        pendente_revisao=True,
    )
    db.session.add(novo)
    db.session.flush()
    return novo


def _criar_spec_se_necessario(material: Material, ingrediente: RecipeIngredient) -> None:
    """Cria registro de spec (Malte/Lupulo/Levedura) em feature_ingredientes
    se ainda não existir para este Material e tipo for conhecido."""
    tipo = (ingrediente.tipo_ingrediente or "").lower()

    if tipo == "fermentavel":
        from addons.addon_brewstation.features.feature_ingredientes.model.malte import Malte
        if not Malte.query.filter_by(material_id=material.id, is_deleted=False).first():
            db.session.add(Malte(
                material_id=material.id,
                cor_ebc=ingrediente.cor_ebc,
                rendimento=ingrediente.rendimento,
            ))

    elif tipo == "lupulo":
        from addons.addon_brewstation.features.feature_ingredientes.model.lupulo import Lupulo
        if not Lupulo.query.filter_by(material_id=material.id, is_deleted=False).first():
            db.session.add(Lupulo(
                material_id=material.id,
                alpha_acidos=ingrediente.alpha_acidos,
            ))

    elif tipo == "levedura":
        from addons.addon_brewstation.features.feature_ingredientes.model.levedura import Levedura
        if not Levedura.query.filter_by(material_id=material.id, is_deleted=False).first():
            db.session.add(Levedura(
                material_id=material.id,
                atenuacao=ingrediente.atenuacao,
            ))


_TIPO_PARA_CATEGORIA = {
    "fermentavel": "materia_prima",
    "lupulo": "materia_prima",
    "levedura": "materia_prima",
}


def cadastrar_todos_pendentes(origem_receita: str = "BrewFather") -> dict:
    """
    Para cada RecipeIngredient pendente da origem dada:
    1. Cria Material em addon_estoque (ou reutiliza se já existir pelo nome)
    2. Cria spec em feature_ingredientes se tipo_ingrediente conhecido
    3. Chama confirmar_mapeamento() — grava cache de-para e resolve todos
       os pendentes com a mesma descricao_origem/origem_receita

    Retorna {"criados": int, "reaproveitados": int, "erros": list[str]}
    """
    pendentes = (
        RecipeIngredient.query
        .filter_by(status_resolucao="pendente_depara", is_deleted=False)
        .join(MashRecipe, RecipeIngredient.recipe_id == MashRecipe.id)
        .filter(MashRecipe.origem_receita == origem_receita)
        .all()
    )

    # Agrupa por descricao_origem pra não processar a mesma descrição N vezes
    grupos: dict[str, RecipeIngredient] = {}
    for ing in pendentes:
        if ing.descricao_origem not in grupos:
            grupos[ing.descricao_origem] = ing

    criados = 0
    reaproveitados = 0
    erros = []

    for descricao, ing in grupos.items():
        try:
            categoria = _TIPO_PARA_CATEGORIA.get(
                (ing.tipo_ingrediente or "").lower(), "materia_prima"
            )
            material = _get_ou_criar_material(descricao, categoria, ing.tipo_ingrediente)

            if material_exists(material.id) and not db.session.is_modified(material):
                reaproveitados += 1
            else:
                criados += 1

            _criar_spec_se_necessario(material, ing)
            db.session.flush()

            confirmar_mapeamento(origem_receita, descricao, material.id)

        except Exception as exc:  # noqa: BLE001
            erros.append(f"{descricao}: {exc}")
            db.session.rollback()

    return {"criados": criados, "reaproveitados": reaproveitados, "erros": erros}
