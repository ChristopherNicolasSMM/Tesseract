"""
addons/addon_estoque/root/services/cotacao_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos

CUSTOMIZAÇÃO (skill 24, Fase 6.1, seção 4): número
"{numero_do_processo}-{sufixo_letra}" (ex.: COT-000001-A,
COT-000001-B) — uma letra por Cotacao dentro do mesmo
ProcessoCotacao, na ordem de criação. Mesma limitação de concorrência
de PedidoCompra.numero (não atômico).
"""


def pbo_apply_fields(obj, data):
    is_create = obj.id is None
    if is_create and not data.get("numero") and data.get("processo_cotacao_id"):
        from core.db import db
        from addons.addon_estoque.root.model.processo_cotacao import ProcessoCotacao
        from addons.addon_estoque.root.model.cotacao import Cotacao

        processo = db.session.get(ProcessoCotacao, int(data["processo_cotacao_id"]))
        if processo:
            existentes = Cotacao.query.filter_by(processo_cotacao_id=processo.id).count()
            sufixo = chr(ord("A") + existentes)  # A, B, C... (não cobre >26 fornecedores no mesmo processo)
            data = dict(data)
            data["numero"] = f"{processo.numero}-{sufixo}"
    return data
