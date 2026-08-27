"""
addons/addon_estoque/root/controller/processo_cotacaos_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.

CUSTOMIZAÇÃO (skill 24, Fase 6.3): ação "gerar-pedido" — mesmo padrão
da ação "receber" de PedidoCompra (skill 23, Fase 4,
controller/pedido_compras_hooks.py): view solta aqui, registro do
`add_url_rule` fica em addon.py (import circular real documentado lá
- este arquivo é importado pelo controller ANTES do blueprint existir).
"""
from flask import flash, redirect, url_for
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_estoque.root.services import estoque_service


def post_create_redirect(processo):
    """
    CUSTOMIZAÇÃO (achado real, sessão pós-Fase 6.3): mesmo raciocínio
    de pedido_compras_hooks.py — sem isso, criar um ProcessoCotacao
    caía na lista, sem indicação de onde convidar fornecedores/
    comparar. Redireciona pro detalhe (abas Cotações/Comparação já
    prontas).
    """
    return redirect(url_for("processo_cotacaos.detail", id=processo.id))


@login_required
@permission_required("processo_cotacaos.update")
def gerar_pedido_view(id: int):
    try:
        resultado = estoque_service.gerar_pedidos_de_cotacao(id)
        n = len(resultado["pedidos_gerados"])
        flash(f"{n} pedido(s) de compra gerado(s) — revise e confirme cada um antes de receber.", "success")
    except estoque_service.ProcessoCotacaoNaoEncontradoError:
        flash("Processo de cotação não encontrado.", "error")
    except ValueError as e:
        flash(str(e), "error")
    except RuntimeError as e:
        flash(str(e), "error")
    return redirect(url_for("processo_cotacaos.detail", id=id))
