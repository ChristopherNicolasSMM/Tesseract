"""
addons/addon_brewstation/features/feature_yeast_bank/controller/yeast_bank_events_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.

`post_create_redirect` (skill 21, estendido na reanálise de
2026-08-24, revisado na skill 22): quando o evento é do tipo
"Contagem de Células", cria automaticamente o registro especializado
(vinculado ao mesmo `bank_item_id` do evento, e agora também ao
próprio evento via `bank_event_id` — skill 22), atualiza o evento com
a FK do registro criado e redireciona a pessoa direto pra tela de
edição dele.

"Starter" (skill 22): deixou de criar registro separado — os campos
específicos (`brew_date`, `target_volume_l`, etc.) já fazem parte do
próprio evento (`YeastStarterLog` foi fundida em `YeastBankEvent`).
Sem redirecionamento nesse caso, mesmo comportamento de
"Descarte"/"Outro".

Quando o tipo é "Descarte", aplica a transição de verdade no
`YeastBankItem` vinculado — captura o status atual do item em
`event.status_before` (automático, `@readonly_fields`) e aplica
`event.status_after` (escolhido na tela; "discarded" por padrão se a
pessoa não escolher) como o novo status do item.
"""
from flask import redirect, url_for

from core.db import db

_DEFAULT_DISCARD_STATUS = "discarded"


def post_create_redirect(event):
    if event.event_type == "Contagem de Células":
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_cell_count_history import (
            YeastCellCountHistory,
        )

        count = YeastCellCountHistory(bank_item_id=event.bank_item_id, bank_event_id=event.id)
        db.session.add(count)
        db.session.flush()

        event.cell_count_id = count.id
        db.session.commit()

        return redirect(url_for("yeast_cell_count_histories.detail", id=count.id))

    if event.event_type == "Descarte":
        item = event.bank_item  # já carregado via relationship, sem query extra

        # status_before é @readonly_fields — nunca vem do formulário,
        # sempre captura o status real do item no momento do evento.
        event.status_before = item.status
        item.status = event.status_after or _DEFAULT_DISCARD_STATUS
        event.status_after = item.status  # garante consistência se o default foi usado

        db.session.commit()

        return None  # sem tabela especializada — fica no manage() padrão

    return None
