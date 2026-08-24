"""
addons/addon_brewstation/features/feature_yeast_bank/controller/yeast_bank_events_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.

`post_create_redirect` (skill 21): quando o evento é do tipo
"Starter" ou "Contagem de Células", cria automaticamente o registro
especializado (vinculado ao mesmo `bank_item_id` do evento),
atualiza o evento com a FK do registro criado e redireciona a
pessoa direto pra tela de edição dele — em vez de voltar pra lista
de eventos.
"""
from flask import redirect, url_for

from core.db import db


def post_create_redirect(event):
    if event.event_type == "Starter":
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_starter_log import (
            YeastStarterLog,
        )

        starter = YeastStarterLog(bank_item_id=event.bank_item_id)
        db.session.add(starter)
        db.session.flush()  # garante starter.id sem fechar a transação ainda

        event.starter_id = starter.id
        db.session.commit()

        return redirect(url_for("yeast_starter_logs.detail", id=starter.id))

    if event.event_type == "Contagem de Células":
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_cell_count_history import (
            YeastCellCountHistory,
        )

        count = YeastCellCountHistory(bank_item_id=event.bank_item_id)
        db.session.add(count)
        db.session.flush()

        event.cell_count_id = count.id
        db.session.commit()

        return redirect(url_for("yeast_cell_count_histories.detail", id=count.id))

    return None
