"""Rotas de emissão opcionais, descobertas no Reports, sob URL do consumidor."""
import secrets
from flask import Blueprint, render_template, session, request, jsonify
from ...root.services import report_emission_service as service
from ...root.api.routes.report_templates_routes import api, payload, output_response
from ...root.services.report_layout_service import ReportError

report_emission_bp = Blueprint('report_emission',__name__)


def screen_view(screen):
    try:
        config=service.authorize(screen)
    except ReportError as exc:
        from flask import abort
        abort(exc.status)
    return render_template('addon_reports/emission.html',screen=screen,label=config[1],icon=config[2],addon=config[3],
                           csrf=session.setdefault('reports_csrf',secrets.token_urlsafe(32)),
                           initial=request.args.to_dict(),fields=service.FILTERS[screen])


@report_emission_bp.get('/brewstation/reports/<screen>')
def brewstation(screen):
    if screen not in service.SCREENS or service.SCREENS[screen][3]!='brewstation':
        from flask import abort
        abort(404)
    return screen_view(screen)


@report_emission_bp.get('/estoque/reports/estoque')
def estoque():
    return screen_view('estoque')


@report_emission_bp.get('/api/reports/emission/<screen>')
@api
def metadata(screen):
    return jsonify(success=True,item=service.metadata(screen)),200,{'Cache-Control':'no-store'}


@report_emission_bp.post('/api/reports/emission/<screen>')
@api
def generate(screen):
    value=payload(('template','version','options','filters','parameters','format'))
    return output_response(service.generate(screen,value),value.get('format','html'))
