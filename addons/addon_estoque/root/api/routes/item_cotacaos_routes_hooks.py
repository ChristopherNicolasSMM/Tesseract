"""
addons/addon_estoque/root/api/routes/item_cotacaos_routes_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.

CUSTOMIZAÇÃO (skill 24, Fase 6.2): ações "selecionar-vencedor" e
"desmarcar-vencedor" — não são CRUD genérico, ficam aqui como funções
soltas (registradas via addon.py com add_url_rule, guardado contra
dupla execução, mesmo padrão da ação "receber" de PedidoCompra — skill
23, Fase 4, controller/pedido_compras_hooks.py — não há risco de
import circular aqui porque este arquivo de rotas API não importa
hooks de volta, mas mantém o mesmo padrão de registro por consistência).
"""
from flask import jsonify
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_estoque.root.services import estoque_service


def _ok(payload: dict, status: int = 200):
    return jsonify({"success": True, **payload}), status


def _erro(mensagem: str, status: int = 400):
    return jsonify({"success": False, "error": mensagem}), status


@login_required
@permission_required("item_cotacaos.update")
def selecionar_vencedor_view(id: int):
    try:
        resultado = estoque_service.selecionar_item_cotacao_vencedor(id)
        return _ok(resultado)
    except estoque_service.ItemCotacaoNaoEncontradoError as e:
        return _erro(str(e), 404)
    except ValueError as e:
        return _erro(str(e), 422)


@login_required
@permission_required("item_cotacaos.update")
def desmarcar_vencedor_view(id: int):
    try:
        resultado = estoque_service.desmarcar_item_cotacao_vencedor(id)
        return _ok(resultado)
    except estoque_service.ItemCotacaoNaoEncontradoError as e:
        return _erro(str(e), 404)
    except ValueError as e:
        return _erro(str(e), 422)
