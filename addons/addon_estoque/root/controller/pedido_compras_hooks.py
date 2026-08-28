"""
addons/addon_estoque/root/controller/pedido_compras_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.

CUSTOMIZAÇÃO (skill 23, Fase 4): ação "receber" — não é CRUD genérico
(CrudGen não gera isso). A view fica aqui (delega toda a regra de
negócio pra estoque_service.receber_pedido_compra() — o controller só
traduz sucesso/erro em flash + redirect, igual ao resto do arquivo
gerado), mas o REGISTRO da rota (`add_url_rule`) fica em addon.py,
não aqui: este módulo é importado por pedido_compras.py ANTES de
`pedido_compras_bp` existir (import circular se tentássemos importar
o blueprint aqui de volta — o try/except ImportError do controller
engoliria o erro em silêncio, sem avisar que a rota nunca foi
registrada). `receber_view` fica só como função pronta pra ser
anexada ao blueprint por quem já tem os dois objetos disponíveis.
"""
from datetime import date

from flask import flash, redirect, url_for, request, jsonify
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_estoque.root.services import estoque_service


def post_create_redirect(pedido):
    """
    CUSTOMIZAÇÃO (achado real, sessão pós-Fase 6.3): o formulário de
    criação (manage.html) só tem os campos de cabeçalho — não há
    "área de itens" ali de propósito (ItemPedidoCompra exige um
    pedido_compra_id já existente, skill 23 Fase 5). Sem este hook, a
    pessoa criava o pedido e caía de volta na LISTA, sem indicação de
    onde adicionar os itens. Redireciona direto pro detalhe (aba
    Itens já pronta) em vez do manage() padrão.
    """
    return redirect(url_for("pedido_compras.detail", id=pedido.id))


@login_required
@permission_required("pedido_compras.update")
def receber_view(id: int):
    try:
        estoque_service.receber_pedido_compra(id)
        flash("Pedido recebido — movimentações de entrada geradas.", "success")
    except estoque_service.PedidoCompraNaoEncontradoError:
        flash("Pedido de compra não encontrado.", "error")
    except estoque_service.PedidoCompraStatusInvalidoError as e:
        flash(str(e), "error")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("pedido_compras.detail", id=id))


@login_required
@permission_required("pedido_compras.update")
def entrada_mercadoria_view(id: int):
    """
    CUSTOMIZAÇÃO (achado do Christopher — "Receber Pedido" era um
    botão cego, sem tela, sem lote/validade): endpoint JSON (não
    redirect — chamado via fetch do modal "Entrada de Mercadoria",
    diferente de receber_view acima que é redirect-based pra
    compatibilidade). Recebe lote_fornecedor/data_validade por item
    (ambos opcionais — decisão de sessão, "pode confirmar sem
    preencher"), repassa pra estoque_service.receber_pedido_compra()
    via dados_por_item. Recebimento continua sempre total (decisão
    original da Fase 4, mantida).

    Body esperado: {"itens": [{"item_pedido_compra_id": int,
    "lote_fornecedor": str|null, "data_validade": "YYYY-MM-DD"|null}, ...]}
    """
    payload = request.get_json(silent=True) or {}
    dados_por_item: dict[int, dict] = {}
    for linha in payload.get("itens", []):
        item_id = linha.get("item_pedido_compra_id")
        if item_id is None:
            continue
        data_validade_raw = linha.get("data_validade")
        data_validade = None
        if data_validade_raw:
            try:
                data_validade = date.fromisoformat(data_validade_raw)
            except ValueError:
                return jsonify({"success": False, "error": f"Data de validade inválida: {data_validade_raw!r}"}), 400
        dados_por_item[int(item_id)] = {
            "lote_fornecedor": (linha.get("lote_fornecedor") or "").strip() or None,
            "data_validade": data_validade,
        }

    try:
        resultado = estoque_service.receber_pedido_compra(id, dados_por_item=dados_por_item)
        return jsonify({"success": True, "pedido_compra": resultado["pedido_compra"]})
    except estoque_service.PedidoCompraNaoEncontradoError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except estoque_service.PedidoCompraStatusInvalidoError as e:
        return jsonify({"success": False, "error": str(e)}), 422
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 422
