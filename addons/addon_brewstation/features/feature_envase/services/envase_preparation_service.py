"""Prévia de embalagem sem escrita; extensão manual, preservada pelo CrudGen."""
from math import isfinite

from addons.addon_estoque.root.services import material_lookup
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.services.ingredient_consumption_service import conferir_ingredientes
from addons.addon_brewstation.features.feature_envase.services.envase_estoque_service import _volume_real_litros, VolumeRealNaoConfiguradoError


class PreparacaoNaoEncontradaError(ValueError):
    """Lote/material inexistente, apagado ou material inativo."""


def _number(value, *, positive=False):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and isfinite(value) and (not positive or value > 0))


def preparar_envase(lote_id: int, material_resultante_id: int, quantidade_litros: float) -> dict:
    """Consulta composição e custo médio atuais, nunca confirma/reserva estoque.

    Quantidades seguem a composição por unidade física, como registrar_envase.
    Custos desconhecidos não viram zero conhecido; subtotal é explicitamente
    parcial. O custo registrado do lote é informado separadamente, sem rateio
    nem recálculo. A permissão e o pertencimento à planta cabem ao controller.
    """
    for identity in (lote_id, material_resultante_id):
        if isinstance(identity, bool) or not isinstance(identity, int) or identity <= 0:
            raise PreparacaoNaoEncontradaError("Selecione um lote e um material resultante válidos.")
    lote = BrewSession.query.filter_by(id=lote_id, is_deleted=False).first()
    if lote is None:
        raise PreparacaoNaoEncontradaError("Lote não encontrado.")
    material = material_lookup.get_material(material_resultante_id)
    if material is None or not material.get("ativo", False):
        raise PreparacaoNaoEncontradaError("Material resultante indisponível ou inativo.")
    try:
        volume = _volume_real_litros(material)
    except VolumeRealNaoConfiguradoError as exc:
        raise ValueError(str(exc)) from exc
    if not _number(volume, positive=True):
        raise ValueError("O volume real convertido do material precisa ser positivo e finito.")
    if not _number(quantidade_litros, positive=True):
        raise ValueError("Informe uma quantidade positiva e finita em litros.")
    units = quantidade_litros / volume
    if not _number(units, positive=True):
        raise ValueError("A quantidade de unidades calculada não é válida.")

    avisos = []
    if not units.is_integer():
        avisos.append("O volume corresponde a unidades fracionadas; revise os litros. A prévia não arredonda quantidades.")
    grouped = {}
    for row in material_lookup.get_composicao(material_resultante_id):
        qty = row["quantidade"]
        if not _number(qty, positive=True):
            raise ValueError("A composição contém quantidade inválida; corrija o cadastro.")
        identity = row["material_componente_id"]
        grouped[identity] = grouped.get(identity, 0.0) + qty
    if not grouped:
        avisos.append("O material resultante não possui composição ativa; confira o cadastro antes de registrar envase.")

    componentes, total, complete = [], 0.0, bool(grouped)
    for identity, qty in grouped.items():
        required = qty * units
        if not _number(required, positive=True):
            raise ValueError("A quantidade total de componente não é válida.")
        component = material_lookup.get_material(identity)
        available = component is not None and component.get("ativo", False)
        label = component["display"] if component else f"Material #{identity}"
        balance = material_lookup.get_saldo(identity)
        if balance and balance.get("is_deleted"):
            balance = None
        base = material_lookup.get_unidade_base(identity)
        unit = base["unidade"] if base else (component or {}).get("unidade_medida")
        price = balance.get("custo_medio") if balance else None
        stock = balance.get("quantidade_atual") if balance else None
        if not _number(stock):
            stock = None
        if not available:
            avisos.append(f"{label}: componente indisponível ou inativo.")
        if not base:
            avisos.append(f"{label}: confira a unidade-base no cadastro; a prévia não converte a composição.")
        if stock is None:
            avisos.append(f"{label}: saldo atual não disponível.")
        elif stock < required:
            avisos.append(f"{label}: quantidade necessária maior que o saldo atual. Este aviso não reserva nem bloqueia estoque.")
        cost = required * price if available and _number(price) and price >= 0 else None
        if cost is not None and not _number(cost):
            raise ValueError("O custo calculado excede os limites numéricos.")
        if cost is None:
            complete = False
            avisos.append(f"{label}: custo médio não disponível; estimativa de embalagem incompleta.")
        else:
            total += cost
        componentes.append({"material_componente_id": identity, "descricao": label,
                            "quantidade_por_unidade": qty, "quantidade_total": required,
                            "unidade": unit, "saldo_atual": stock, "custo_medio": price if cost is not None else None,
                            "custo_estimado": cost})
    if not _number(total):
        raise ValueError("O custo total excede os limites numéricos.")

    confirmed = lote.insumos_baixados_em is not None
    pending = []
    if not confirmed:
        avisos.append("Ao registrar envase pelo fluxo existente, os ingredientes ainda não confirmados serão consumidos junto com as embalagens. Esta prévia não confirma ingredientes.")
        if lote.recipe_id:
            pending = conferir_ingredientes(lote.recipe_id)["pendencias"]
            if pending:
                avisos.append(f"Existem {len(pending)} pendência(s) de ingredientes que impedem o registro pelo serviço de envase.")
        else:
            avisos.append("O lote não possui receita vinculada; o serviço de registro exige receita para confirmar ingredientes.")
    return {"lote_id": lote_id, "material_resultante_id": material_resultante_id,
            "material_descricao": material["display"], "quantidade_litros": quantidade_litros,
            "volume_por_unidade_litros": volume, "unidades_geradas": units,
            "componentes": componentes, "custo_embalagem_estimado": total,
            "custo_embalagem_completo": complete, "avisos": avisos,
            "insumos_confirmados": confirmed, "pendencias_ingredientes": pending,
            "custo_registrado_lote": lote.custo_total_insumos if confirmed else None}
