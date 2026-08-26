"""
addons/addon_estoque/root/services/processo_cotacao_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos

CUSTOMIZAÇÃO (skill 24, Fase 6.1): número sequencial automático
(COT-000001), mesmo padrão de PedidoCompra (skill 23, Fase 4, mesma
limitação de concorrência documentada lá).
"""


def pbo_apply_fields(obj, data):
    is_create = obj.id is None
    if is_create and not data.get("numero"):
        from addons.addon_estoque.root.model.processo_cotacao import ProcessoCotacao
        ultimo = ProcessoCotacao.query.order_by(ProcessoCotacao.id.desc()).first()
        proximo_num = (ultimo.id + 1) if ultimo else 1
        data = dict(data)
        data["numero"] = f"COT-{proximo_num:06d}"
    return data
