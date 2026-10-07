"""Navegação após criação atômica: nenhum efeito de negócio no controller."""
from flask import redirect, url_for
from flask_login import current_user


def post_create_redirect(event):
    if event.event_type == 'Contagem de Células' and event.cell_count_id and current_user.is_authenticated and current_user.has_permission('yeast_cell_count_histories.detail'):
        return redirect(url_for('yeast_cell_count_histories.detail', id=event.cell_count_id))
    return None
