"""Views de extensão dos blueprints de compras; autenticação/CSRF existentes."""
from flask import request, jsonify, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from core.permissions import permission_required
from services.core.organization_service import list_organizations
from addons.addon_estoque.root.services.purchase_context_service import document, get_context, bind_context


def _view(kind, ident):
    try:
        obj = document(kind, ident)
    except ValueError:
        abort(404)
    if request.method == 'POST':
        data = request.get_json(silent=True) if request.is_json else {'organization_code': request.form.get('organization_code')}
        result = bind_context(kind, ident, data, actor=current_user.username)
        if request.is_json:
            return jsonify(success=result.success, data=result.data, error=result.error), result.code
        flash('Contexto organizacional registrado.' if result.success else result.error,
              'success' if result.success else 'error')
        if result.success:
            return redirect(request.path)
        status = result.code
    else:
        status = 200
    blueprint = 'pedido_compras' if kind == 'order' else 'processo_cotacaos'
    context = get_context(kind, ident)
    if request.is_json:
        return jsonify(success=True, data=context.to_dict() if context else None)
    return render_template('purchase_context/detail.html', item=obj, context=context,
                           organizations=[org for org in list_organizations() if org.is_active],
                           document_url=url_for(blueprint + '.detail', id=ident)), status


@login_required
@permission_required('pedido_compras.update')
def order_context_view(id):
    return _view('order', id)


@login_required
@permission_required('processo_cotacaos.update')
def process_context_view(id):
    return _view('process', id)
