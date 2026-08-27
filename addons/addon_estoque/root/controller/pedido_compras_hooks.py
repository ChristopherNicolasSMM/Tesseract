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
from flask import flash, redirect, url_for
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
