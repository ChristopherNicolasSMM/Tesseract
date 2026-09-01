"""
addons/addon_brewstation/features/feature_envase/services/envase_estoque_service.py

Reescrito na skill 26 (docs/skills/26-proposta-envase-consumo-insumo-custo-industrializacao.md)
— Envase passa a apontar pro Material resultante (produto acabado,
ex. "Growler 1L Valirian Pilsen"); os componentes de embalagem
(rótulo/tampa/caixa) deixam de ser digitados um a um em ItemEnvase e
passam a ser resolvidos automaticamente pela Composição (BOM) do
Material resultante. `ItemEnvase` fica só como registro histórico do
que existia antes desta rodada — não é mais criado aqui.

Nao e gerado pelo CrudGen (mesmo papel de ingredient_resolution_service.py
em feature_mash_control) - orquestra Envase e chama addon_estoque de
forma sincrona pra dar baixa nos Materiais de embalagem usados. Ver
addons/addon_brewstation/features/feature_envase/docs/technical/03-fluxos.md.

Nome distinto de envase_service.py (esse sim gerado pelo CrudGen,
CRUD genérico de Envase) — evita colisão de nome de arquivo dentro da
mesma pasta services/.
"""
from __future__ import annotations

from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_envase.model.envase import Envase
from addons.addon_brewstation.features.feature_mash_control.services import ingredient_consumption_service
from addons.addon_estoque.root.services import estoque_service, material_lookup


class LoteNaoEncontradoError(Exception):
    pass


class MaterialNaoEncontradoError(Exception):
    pass


class VolumeRealNaoConfiguradoError(Exception):
    pass


def registrar_envase(
    lote_id: int,
    material_resultante_id: int,
    quantidade_litros: float,
    *,
    data_envase=None,
    tipo_envase: str | None = None,
) -> dict:
    """
    Registra um Envase apontando pro Material resultante (produto
    acabado) e dá baixa síncrona nos componentes de embalagem
    resolvidos pela Composição desse Material (skill 26) — nunca mais
    digitados um a um em ItemEnvase.

    Fluxo:
    1. Valida lote e Material resultante.
    2. Fallback de insumo (seção 2.1 da skill): se o lote ainda não
       teve seus insumos de receita baixados
       (`BrewSession.insumos_baixados_em is None`), confirma agora,
       antes de prosseguir — nunca deixa um Envase acontecer sem o
       custo de insumo do lote rastreado.
    3. Cria o Envase.
    4. Resolve unidades físicas geradas
       (`quantidade_litros / Material.volume_real`) e, pra cada
       componente da Composição do Material resultante, dá baixa de
       `quantidade_componente × unidades` via `registrar_movimentacao`.
    5. Retorna o Envase + o detalhe de custo (seção 3.3 da skill).
    """
    lote = BrewSession.query.filter_by(id=lote_id, is_deleted=False).first()
    if lote is None:
        raise LoteNaoEncontradoError(f"BrewSession id={lote_id} não encontrada ou removida")

    material_resultante = material_lookup.get_material(material_resultante_id)
    if material_resultante is None:
        raise MaterialNaoEncontradoError(f"Material id={material_resultante_id} não encontrado em addon_estoque")

    volume_real = material_resultante.get("volume_real")
    if not volume_real or volume_real <= 0:
        raise VolumeRealNaoConfiguradoError(
            f"Material '{material_resultante.get('display')}' (id={material_resultante_id}) "
            "não tem volume_real configurado — sem isso não é possível calcular quantas "
            "unidades este Envase gera."
        )

    if lote.insumos_baixados_em is None:
        ingredient_consumption_service.confirmar_consumo_ingredientes(lote_id)

    envase = Envase(
        lote_id=lote_id,
        material_resultante_id=material_resultante_id,
        quantidade_litros=quantidade_litros,
        data_envase=data_envase,
        tipo_envase=tipo_envase,
        status="registrado",
    )
    db.session.add(envase)
    db.session.commit()

    unidades_geradas = quantidade_litros / volume_real
    componentes = material_lookup.get_composicao(material_resultante_id)

    movimentacoes = []
    for componente in componentes:
        quantidade_total = componente["quantidade"] * unidades_geradas
        resultado = estoque_service.registrar_movimentacao(
            componente["material_componente_id"], "saida", quantidade_total,
            observacoes=f"Baixa de componente de embalagem — Envase #{envase.id} (lote #{lote_id}).",
        )
        movimentacoes.append(resultado)

    return {
        "envase": envase.to_dict(),
        "unidades_geradas": unidades_geradas,
        "componentes_baixados": len(componentes),
        "movimentacoes": movimentacoes,
    }


def calcular_custo_industrializacao_envase(envase_id: int) -> dict:
    """
    Custo real de industrialização de um Envase (seção 3.3 da skill
    26) — parte cerveja (rateada da receita pelo volume) + parte
    componentes (Composição do Material resultante, já pelo custo
    médio de cada componente).

    `litros_produzidos_do_lote` = soma de `Envase.quantidade_litros`
    de todos os Envases (não apagados) do mesmo lote — inclui o
    próprio Envase consultado.
    """
    envase = db.session.get(Envase, envase_id)
    if envase is None or envase.is_deleted:
        raise LoteNaoEncontradoError(f"Envase id={envase_id} não encontrado ou removido")

    lote = envase.lote
    litros_produzidos_do_lote = db.session.query(
        db.func.coalesce(db.func.sum(Envase.quantidade_litros), 0.0)
    ).filter(Envase.lote_id == envase.lote_id, Envase.is_deleted.is_(False)).scalar()

    custo_cerveja = 0.0
    if lote.custo_total_insumos and litros_produzidos_do_lote:
        custo_por_litro = lote.custo_total_insumos / litros_produzidos_do_lote
        custo_cerveja = custo_por_litro * (envase.quantidade_litros or 0.0)

    custo_componentes = 0.0
    detalhe_componentes = []
    if envase.material_resultante_id:
        material_resultante = material_lookup.get_material(envase.material_resultante_id)
        volume_real = (material_resultante or {}).get("volume_real") or 0
        unidades_geradas = (envase.quantidade_litros / volume_real) if volume_real else 0
        for componente in material_lookup.get_composicao(envase.material_resultante_id):
            saldo = material_lookup.get_saldo(componente["material_componente_id"])
            custo_medio = saldo.get("custo_medio") if saldo else None
            quantidade_total = componente["quantidade"] * unidades_geradas
            custo_linha = (quantidade_total * custo_medio) if custo_medio is not None else None
            if custo_linha is not None:
                custo_componentes += custo_linha
            detalhe_componentes.append({
                "material_componente_id": componente["material_componente_id"],
                "quantidade_total": quantidade_total,
                "custo_medio": custo_medio,
                "custo_linha": custo_linha,
            })

    return {
        "envase_id": envase_id,
        "custo_cerveja": custo_cerveja,
        "custo_componentes": custo_componentes,
        "custo_total_industrializacao": custo_cerveja + custo_componentes,
        "detalhe_componentes": detalhe_componentes,
    }
