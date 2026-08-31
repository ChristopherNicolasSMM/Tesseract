"""
addons/addon_estoque/root/controller/materials_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.

CUSTOMIZAÇÃO (achado do Christopher — ações em massa a partir da
seleção de linhas na lista de Materiais): 4 endpoints JSON novos, não
CRUD genérico. Mesmo padrão já usado em pedido_compras_hooks.py/
processo_cotacaos_hooks.py — view solta aqui, `add_url_rule` fica em
addon.py (evita o mesmo risco de import circular já documentado lá).
"""
from flask import request, jsonify
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_estoque.root.services import estoque_service


def _erro_json(mensagem: str, status: int = 400):
    return jsonify({"success": False, "error": mensagem}), status


@login_required
@permission_required("materials.update")
def movimentar_em_massa_view():
    payload = request.get_json(silent=True) or {}
    tipo_movimentacao = payload.get("tipo_movimentacao")
    itens = payload.get("itens") or []
    if not tipo_movimentacao or not itens:
        return _erro_json("Informe tipo_movimentacao e ao menos um item.")

    resultado = estoque_service.movimentar_estoque_em_massa(tipo_movimentacao, itens)
    falhas = [r for r in resultado["resultados"] if not r["sucesso"]]
    return jsonify({
        "success": not falhas,
        "resultados": resultado["resultados"],
        "error": f"{len(falhas)} de {len(itens)} item(ns) falharam — veja o detalhe por linha." if falhas else None,
    })


@login_required
@permission_required("processo_cotacaos.create")
def criar_cotacao_em_massa_view():
    payload = request.get_json(silent=True) or {}
    itens = payload.get("itens") or []
    if not itens:
        return _erro_json("Selecione ao menos um Material.")

    try:
        resultado = estoque_service.criar_processo_cotacao_em_massa(
            itens,
            processo_cotacao_id=payload.get("processo_cotacao_id"),
            novo_processo=payload.get("novo_processo"),
        )
        return jsonify({"success": True, **resultado})
    except (ValueError, RuntimeError) as e:
        return _erro_json(str(e), 422)
    except estoque_service.ProcessoCotacaoNaoEncontradoError as e:
        return _erro_json(str(e), 404)


@login_required
@permission_required("pedido_compras.create")
def criar_pedido_em_massa_view():
    payload = request.get_json(silent=True) or {}
    itens = payload.get("itens") or []
    if not itens:
        return _erro_json("Selecione ao menos um Material.")

    try:
        resultado = estoque_service.criar_pedido_compra_em_massa(
            itens,
            pedido_compra_id=payload.get("pedido_compra_id"),
            novo_pedido=payload.get("novo_pedido"),
        )
        return jsonify({"success": True, **resultado})
    except (ValueError, RuntimeError) as e:
        return _erro_json(str(e), 422)
    except estoque_service.PedidoCompraNaoEncontradoError as e:
        return _erro_json(str(e), 404)
    except estoque_service.PedidoCompraStatusInvalidoError as e:
        return _erro_json(str(e), 422)


@login_required
@permission_required("materials.update")
def modificar_em_massa_view():
    payload = request.get_json(silent=True) or {}
    material_ids = payload.get("material_ids") or []
    alteracoes = payload.get("alteracoes") or {}
    if not material_ids:
        return _erro_json("Selecione ao menos um Material.")

    try:
        resultado = estoque_service.modificar_materiais_em_massa(material_ids, alteracoes)
        return jsonify({"success": True, **resultado})
    except ValueError as e:
        return _erro_json(str(e), 422)
