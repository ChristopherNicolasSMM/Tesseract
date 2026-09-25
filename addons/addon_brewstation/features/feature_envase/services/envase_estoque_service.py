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

from math import isfinite
from datetime import datetime, timezone

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


class EnvaseNaoEstornavelError(ValueError):
    pass


def _volume_real_litros(material: dict) -> float:
    volume = material.get("volume_real")
    unidade = (material.get("unidade_medida_volume_real") or "L").strip().lower()
    if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not isfinite(volume) or volume <= 0:
        raise VolumeRealNaoConfiguradoError("O produto acabado precisa ter volume real positivo.")
    if unidade in ("l", "lt", "litro", "litros"):
        return volume
    if unidade in ("ml", "mililitro", "mililitros", "cm3"):
        return volume / 1000
    if unidade == "m3":
        return volume * 1000
    raise VolumeRealNaoConfiguradoError(f"Unidade do volume real não suportada: {unidade}")


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

    volume_real = _volume_real_litros(material_resultante)
    if isinstance(quantidade_litros, bool) or not isinstance(quantidade_litros, (int, float)) or not isfinite(quantidade_litros) or quantidade_litros <= 0:
        raise ValueError("A quantidade de envase deve ser um número positivo e finito em litros.")

    unidades_geradas = quantidade_litros / volume_real
    componentes = material_lookup.get_composicao(material_resultante_id)

    try:
        if lote.insumos_baixados_em is None:
            ingredient_consumption_service.confirmar_consumo_ingredientes(lote_id, commit=False)

        envase = Envase(
            lote_id=lote_id,
            material_resultante_id=material_resultante_id,
            quantidade_litros=quantidade_litros,
            data_envase=data_envase,
            tipo_envase=tipo_envase,
            status="registrado",
            componentes_snapshot=[],
        )
        db.session.add(envase)
        db.session.flush()

        movimentacoes = []
        snapshot = []
        for componente in componentes:
            quantidade_total = componente["quantidade"] * unidades_geradas
            if not isfinite(quantidade_total) or quantidade_total <= 0:
                raise ValueError("Composição do produto acabado contém quantidade inválida.")
            saldo = material_lookup.get_saldo(componente["material_componente_id"])
            custo_medio = saldo.get("custo_medio") if saldo else None
            resultado = estoque_service.registrar_movimentacao(
                componente["material_componente_id"], "saida", quantidade_total,
                custo_unitario=custo_medio,
                observacoes=f"Baixa de componente de embalagem — Envase #{envase.id} (lote #{lote_id}).",
                commit=False,
            )
            movimentacoes.append(resultado)
            snapshot.append({
                "material_componente_id": componente["material_componente_id"],
                "quantidade_por_unidade": componente["quantidade"],
                "quantidade_total": quantidade_total,
                "custo_medio": custo_medio,
                "custo_linha": resultado["movimentacao"].get("custo_total"),
                "movimentacao_id": resultado["movimentacao"]["id"],
            })
        envase.componentes_snapshot = snapshot
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return {
        "envase": envase.to_dict(),
        "unidades_geradas": unidades_geradas,
        "componentes_baixados": len(componentes),
        "movimentacoes": movimentacoes,
    }


def estornar_envase(envase_id: int, motivo: str, *, usuario_id: int | None = None) -> dict:
    """Devolve embalagens pela mesma regra de estoque e cancela o envase atomicamente.

    Ingredientes são consumo do lote, não deste envase, e não são estornados.
    Envases antigos sem fotografia de movimentos exigem reconciliação manual.
    """
    from addons.addon_estoque.root.model.movimentacao import Movimentacao

    envase = db.session.get(Envase, envase_id)
    if envase is None or envase.is_deleted:
        raise EnvaseNaoEstornavelError("Envase não encontrado.")
    if envase.status != "registrado":
        raise EnvaseNaoEstornavelError("Este envase já foi cancelado.")
    if envase.componentes_snapshot is None:
        raise EnvaseNaoEstornavelError("Envase antigo sem movimentos identificados: requer reconciliação manual.")
    if not isinstance(motivo, str) or not motivo.strip():
        raise EnvaseNaoEstornavelError("Informe o motivo do estorno.")

    try:
        # Reserva o cancelamento na mesma transação: uma segunda tentativa
        # concorrente não pode devolver as mesmas saídas novamente.
        claimed = Envase.query.filter_by(id=envase_id, status="registrado").update(
            {"status": "cancelado"}, synchronize_session="fetch",
        )
        if claimed != 1:
            raise EnvaseNaoEstornavelError("Este envase já foi cancelado.")
        devolucoes = []
        for componente in envase.componentes_snapshot:
            original = db.session.get(Movimentacao, componente["movimentacao_id"])
            if (original is None or original.is_deleted or original.tipo_movimentacao != "saida"
                    or original.material_id != componente["material_componente_id"]
                    or original.quantidade != componente["quantidade_total"]):
                raise EnvaseNaoEstornavelError("A saída original não corresponde ao registro do envase.")
            resultado = estoque_service.registrar_movimentacao(
                original.material_id, "entrada", original.quantidade,
                custo_unitario=original.custo_unitario,
                usuario_id=usuario_id,
                observacoes=f"Estorno Envase #{envase.id}, saída #{original.id}: {motivo.strip()}",
                commit=False,
            )
            devolucoes.append({"saida_id": original.id,
                               "entrada_id": resultado["movimentacao"]["id"]})
        envase.cancelado_em = datetime.now(timezone.utc)
        envase.motivo_cancelamento = motivo.strip()
        envase.cancelado_por_id = usuario_id
        envase.estorno_snapshot = devolucoes
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return {"envase": envase.to_dict(), "devolucoes": devolucoes}


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
    if envase.status == "cancelado":
        raise EnvaseNaoEstornavelError("Envase cancelado não compõe o custo de produção.")

    lote = envase.lote
    litros_produzidos_do_lote = db.session.query(
        db.func.coalesce(db.func.sum(Envase.quantidade_litros), 0.0)
    ).filter(Envase.lote_id == envase.lote_id, Envase.is_deleted.is_(False), Envase.status == "registrado").scalar()

    custo_cerveja = 0.0
    if lote.custo_total_insumos and litros_produzidos_do_lote:
        custo_por_litro = lote.custo_total_insumos / litros_produzidos_do_lote
        custo_cerveja = custo_por_litro * (envase.quantidade_litros or 0.0)

    custo_componentes = 0.0
    detalhe_componentes = []
    if envase.componentes_snapshot is not None:
        detalhe_componentes = envase.componentes_snapshot
        custo_componentes = sum(
            componente["custo_linha"] for componente in detalhe_componentes
            if componente.get("custo_linha") is not None
        )
    elif envase.material_resultante_id:
        material_resultante = material_lookup.get_material(envase.material_resultante_id)
        volume_real = _volume_real_litros(material_resultante) if material_resultante and material_resultante.get("volume_real") else 0
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
        "componentes_historicos": envase.componentes_snapshot is not None,
        "custo_cerveja": custo_cerveja,
        "custo_componentes": custo_componentes,
        "custo_total_industrializacao": custo_cerveja + custo_componentes,
        "detalhe_componentes": detalhe_componentes,
    }
