"""
addons/addon_estoque/root/services/estoque_service.py

API pública rica do addon_estoque, além do CRUD genérico já gerado em
material_service.py/movimentacao_service.py/saldo_service.py. Não é
gerado pelo CrudGen (mesmo papel de device_service.py em
addon_device_manager) — é o ponto de extensão estável para a lógica
de negócio (registrar movimentação + atualizar saldo em conjunto).

Regra de negócio: toda movimentação passa por aqui, nunca por INSERT
direto em Movimentacao a partir de outro módulo — é este service que
garante Movimentacao (ledger) e Saldo (cache) ficarem consistentes na
mesma operação.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.movimentacao import Movimentacao
from addons.addon_estoque.root.model.saldo import Saldo

TIPOS_VALIDOS = ("entrada", "saida", "ajuste")


class MaterialNaoEncontradoError(Exception):
    pass


class TipoMovimentacaoInvalidoError(Exception):
    pass


def _get_or_create_saldo(material_id: int) -> Saldo:
    saldo = Saldo.query.filter_by(material_id=material_id).first()
    if saldo is None:
        saldo = Saldo(material_id=material_id, quantidade_atual=0.0)
        db.session.add(saldo)
        db.session.flush()
    return saldo


def registrar_movimentacao(
    material_id: int,
    tipo_movimentacao: str,
    quantidade: float,
    *,
    custo_unitario: float | None = None,
    lote_fornecedor: str | None = None,
    data_validade=None,
    usuario_id: int | None = None,
    observacoes: str | None = None,
) -> dict:
    """
    Registra uma Movimentacao (ledger, imutável) e atualiza o Saldo
    (cache) na mesma transação. "ajuste" pode ser positivo (entrada
    corretiva) ou negativo (saída corretiva) — quantidade aceita
    qualquer sinal só para tipo_movimentacao="ajuste"; "entrada"/
    "saida" exigem quantidade >= 0 (o sinal é dado pelo tipo).

    Retorna dict primitivo (nunca o objeto ORM) — mesma regra de
    fronteira usada em device_manager (skill 05, seção 6).
    """
    if tipo_movimentacao not in TIPOS_VALIDOS:
        raise TipoMovimentacaoInvalidoError(
            f"tipo_movimentacao deve ser um de {TIPOS_VALIDOS}, recebido: {tipo_movimentacao!r}"
        )

    material = Material.query.filter_by(id=material_id, is_deleted=False).first()
    if material is None:
        raise MaterialNaoEncontradoError(f"Material id={material_id} não encontrado ou removido")

    if tipo_movimentacao in ("entrada", "saida") and quantidade < 0:
        raise ValueError("quantidade não pode ser negativa para entrada/saida — use tipo_movimentacao='ajuste'")

    custo_total = (custo_unitario * quantidade) if custo_unitario is not None else None

    movimentacao = Movimentacao(
        material_id=material_id,
        tipo_movimentacao=tipo_movimentacao,
        quantidade=quantidade,
        custo_unitario=custo_unitario,
        custo_total=custo_total,
        lote_fornecedor=lote_fornecedor,
        data_validade=data_validade,
        data_movimentacao=datetime.now(timezone.utc),
        usuario_id=usuario_id,
        observacoes=observacoes,
    )
    db.session.add(movimentacao)

    saldo = _get_or_create_saldo(material_id)

    if tipo_movimentacao == "entrada":
        _aplicar_entrada(saldo, quantidade, custo_unitario)
    elif tipo_movimentacao == "saida":
        saldo.quantidade_atual -= quantidade
    else:  # ajuste — sinal já vem embutido em quantidade
        if quantidade > 0 and custo_unitario is not None:
            _aplicar_entrada(saldo, quantidade, custo_unitario)
        else:
            saldo.quantidade_atual += quantidade

    if saldo.custo_medio is not None:
        saldo.valor_total_estoque = saldo.quantidade_atual * saldo.custo_medio
    saldo.ultima_atualizacao = datetime.now(timezone.utc)

    db.session.commit()

    return {
        "movimentacao": movimentacao.to_dict(),
        "saldo": saldo.to_dict(),
    }


def _aplicar_entrada(saldo: Saldo, quantidade: float, custo_unitario: float | None) -> None:
    """Custo médio ponderado: (saldo_atual*custo_medio_atual + entrada*custo_entrada) / (saldo_atual+entrada)."""
    quantidade_anterior = saldo.quantidade_atual
    custo_medio_anterior = saldo.custo_medio or 0.0

    saldo.quantidade_atual = quantidade_anterior + quantidade

    if custo_unitario is not None and saldo.quantidade_atual > 0:
        valor_anterior = quantidade_anterior * custo_medio_anterior
        valor_entrada = quantidade * custo_unitario
        saldo.custo_medio = (valor_anterior + valor_entrada) / saldo.quantidade_atual


def consultar_saldo(material_id: int) -> dict | None:
    saldo = Saldo.query.filter_by(material_id=material_id).first()
    return saldo.to_dict() if saldo else None
