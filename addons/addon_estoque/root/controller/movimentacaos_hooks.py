"""
addons/addon_estoque/root/controller/movimentacaos_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.
"""

from flask import request, render_template
from flask_login import login_required
from core.permissions import permission_required
from ..model.movimentacao import Movimentacao
from ..model.material import Material


@login_required
@permission_required('movimentacaos.list')
def legacy_history_view():
    try:
        page = int(request.args.get('page', '1'))
        if not 1 <= page <= 1000000: raise ValueError
    except ValueError:
        page = 1
    rows = Movimentacao.query.order_by(Movimentacao.id.desc()).limit(51).offset((page - 1) * 50).all()
    ids = {row.material_id for row in rows}
    names = {row.id: row.nome for row in Material.query.filter(Material.id.in_(ids)).all()}
    return render_template('organization_stock/legacy_history.html', movements=rows[:50], names=names,
                           page=page, has_next=len(rows) > 50)


def protect_legacy_history_screen():
    if request.endpoint == 'movimentacaos.manage' and request.method == 'GET':
        return legacy_history_view()
