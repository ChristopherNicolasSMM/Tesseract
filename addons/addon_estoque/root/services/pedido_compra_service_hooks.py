"""
addons/addon_estoque/root/services/pedido_compra_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos

CUSTOMIZAÇÃO (skill 23, Fase 4): geração automática de `numero`
sequencial (formato PC-000001) quando não informado no create — mesmo
espírito do `sku` de Material (gerado, mas editável depois, nunca
travado). Só gera no create (obj.id ainda None); update nunca
sobrescreve um numero já setado.

LIMITAÇÃO CONHECIDA: `ultimo.id + 1` não é atômico sob concorrência
real (duas criações simultâneas poderiam calcular o mesmo próximo
número antes de qualquer commit) — aceitável para o volume de uso
esperado nesta fase; se isso virar problema real, trocar por
sequência de banco dedicada.
"""
from core.db import db


def pbo_apply_fields(obj, data):
    is_create = obj.id is None
    if is_create and not data.get("numero"):
        from addons.addon_estoque.root.model.pedido_compra import PedidoCompra
        ultimo = PedidoCompra.query.order_by(PedidoCompra.id.desc()).first()
        proximo_num = (ultimo.id + 1) if ultimo else 1
        data = dict(data)
        data["numero"] = f"PC-{proximo_num:06d}"
    return data
