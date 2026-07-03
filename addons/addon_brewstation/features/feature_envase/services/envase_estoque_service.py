"""
addons/addon_brewstation/features/feature_envase/services/envase_estoque_service.py

Nao e gerado pelo CrudGen (mesmo papel de ingredient_resolution_service.py
em feature_mash_control) - orquestra Envase/ItemEnvase e chama
addon_estoque de forma sincrona pra dar baixa nos Materiais de
embalagem usados. Ver
addons/addon_brewstation/features/feature_envase/docs/technical/03-fluxos.md.

Nome distinto de envase_service.py (esse sim gerado pelo CrudGen,
CRUD genérico de Envase) — evita colisão de nome de arquivo dentro da
mesma pasta services/.
"""
from __future__ import annotations

from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_envase.model.envase import Envase
from addons.addon_brewstation.features.feature_envase.model.item_envase import ItemEnvase
from addons.addon_estoque.root.services import estoque_service, material_lookup


class LoteNaoEncontradoError(Exception):
    pass


class MaterialNaoEncontradoError(Exception):
    pass


def registrar_envase(
    lote_id: int,
    itens: list[dict],
    *,
    quantidade_litros: float | None = None,
    data_envase=None,
    tipo_envase: str | None = None,
) -> dict:
    """
    Registra um Envase + seus ItemEnvase, e dá baixa síncrona no
    estoque de cada Material usado (skill 02: comunicação cross-Addon
    via service público, nunca FK — aqui é chamada direta porque a
    baixa tem que acontecer junto com o registro, não eventualmente).

    `itens`: lista de {"material_id": int, "quantidade": float}.

    Se qualquer item referenciar um Material inexistente, nada é
    gravado (toda a operação falha antes do primeiro INSERT).
    """
    lote = BrewSession.query.filter_by(id=lote_id, is_deleted=False).first()
    if lote is None:
        raise LoteNaoEncontradoError(f"BrewSession id={lote_id} não encontrada ou removida")

    for item in itens:
        if not material_lookup.material_exists(item["material_id"]):
            raise MaterialNaoEncontradoError(f"Material id={item['material_id']} não encontrado em addon_estoque")

    envase = Envase(
        lote_id=lote_id,
        quantidade_litros=quantidade_litros,
        data_envase=data_envase,
        tipo_envase=tipo_envase,
        status="registrado",
    )
    db.session.add(envase)
    db.session.flush()  # garante envase.id sem commitar ainda

    itens_criados = []
    for item in itens:
        item_envase = ItemEnvase(
            envase_id=envase.id,
            material_id=item["material_id"],
            quantidade=item["quantidade"],
        )
        db.session.add(item_envase)
        itens_criados.append(item_envase)

    db.session.commit()

    movimentacoes = []
    for item in itens:
        resultado = estoque_service.registrar_movimentacao(
            item["material_id"], "saida", item["quantidade"],
        )
        movimentacoes.append(resultado)

    return {
        "envase": envase.to_dict(),
        "itens": [i.to_dict() for i in itens_criados],
        "movimentacoes": movimentacoes,
    }
