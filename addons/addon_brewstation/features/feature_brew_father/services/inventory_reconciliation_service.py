"""Conciliação de leitura entre o ledger do Estoque e o Brewfather.

Não publica saldos nem cria movimentações. O de-para de receitas fornece
apenas sugestões; o vínculo por ID remoto requer confirmação explícita.
"""
from decimal import Decimal, InvalidOperation

from core.db import db
from addons.addon_estoque.root.services import material_lookup
from addons.addon_brewstation.features.feature_brew_father.model.inventory_link import BrewfatherInventoryLink
from addons.addon_brewstation.features.feature_mash_control.model.ingredient_mapping import IngredientMapping


CATEGORIAS = {"fermentables": "kg", "hops": "g"}


def _quantidade(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = Decimal(str(valor))
        return numero if numero.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def listar_vinculos(categoria: str) -> dict[str, BrewfatherInventoryLink]:
    if categoria not in CATEGORIAS:
        raise ValueError("Categoria de conciliação não suportada.")
    return {v.remote_id: v for v in BrewfatherInventoryLink.query.filter_by(categoria=categoria).all()}


def sugestao_depara(nome: str) -> dict | None:
    mapping = IngredientMapping.query.filter_by(
        origem_receita="BrewFather", descricao_origem=nome, is_deleted=False,
    ).first()
    return material_lookup.get_material(mapping.material_id) if mapping else None


def visualizar_item(categoria: str, remoto: dict, vinculo: BrewfatherInventoryLink | None) -> dict:
    if categoria not in CATEGORIAS:
        raise ValueError("Categoria de conciliação não suportada.")
    dados = {"material": None, "unidade_base": None, "saldo_local": None,
             "quantidade_publicavel": None, "diferenca": None,
             "unidade_brewfather": CATEGORIAS[categoria], "bloqueios": []}
    if not vinculo:
        dados["bloqueios"].append("Vincule um Material antes de comparar saldos.")
        return dados
    material = material_lookup.get_material(vinculo.material_id)
    dados["material"] = material
    if not material or not material.get("ativo"):
        dados["bloqueios"].append("Material removido ou inativo.")
        return dados
    if material.get("pendente_revisao"):
        dados["bloqueios"].append("Revise os dados do Material antes de publicar seu cadastro.")

    unidade = material_lookup.get_unidade_base(vinculo.material_id)
    saldo = material_lookup.get_saldo(vinculo.material_id)
    dados["unidade_base"] = unidade["unidade"] if unidade else None
    dados["saldo_local"] = saldo["quantidade_atual"] if saldo else None
    if not unidade or not saldo:
        dados["bloqueios"].append("Unidade base ou saldo ausente no Estoque.")
        return dados

    quantidade = _quantidade(saldo["quantidade_atual"])
    if quantidade is None or quantidade < 0:
        dados["bloqueios"].append("Saldo local inválido ou negativo.")
        return dados
    base, destino = unidade["unidade"].upper(), CATEGORIAS[categoria]
    if base == "KG" and destino == "g":
        quantidade *= 1000
    elif base == "G" and destino == "kg":
        quantidade /= 1000
    elif base != destino.upper():
        dados["bloqueios"].append(f"Conversão de {base} para {destino} não definida; revise a unidade base do Material.")
        return dados

    dados["quantidade_publicavel"] = float(quantidade)
    remoto_qtd = _quantidade(remoto.get("inventory"))
    if remoto_qtd is not None:
        dados["diferenca"] = float(quantidade - remoto_qtd)
    return dados


def vincular(categoria: str, remote_id: str, material_id: int) -> BrewfatherInventoryLink:
    if categoria not in CATEGORIAS or not remote_id or len(remote_id) > 100:
        raise ValueError("Item remoto inválido para esta categoria.")
    material = material_lookup.get_material(material_id)
    if not material or not material.get("ativo"):
        raise ValueError("Selecione um Material ativo do Estoque.")
    outro = BrewfatherInventoryLink.query.filter_by(categoria=categoria, material_id=material_id).first()
    if outro and outro.remote_id != remote_id:
        raise ValueError("Este Material já está vinculado a outro item desta categoria no Brewfather.")
    vinculo = BrewfatherInventoryLink.query.filter_by(categoria=categoria, remote_id=remote_id).first()
    if vinculo is None:
        vinculo = BrewfatherInventoryLink(categoria=categoria, remote_id=remote_id, material_id=material_id)
        db.session.add(vinculo)
    else:
        vinculo.material_id = material_id
    db.session.commit()
    return vinculo
