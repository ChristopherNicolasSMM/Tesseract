"""DTO público de sessão v1. Não executa polling, alarmes ou recalculo."""
from decimal import Decimal
from flask import abort
from flask_login import current_user
from core.db import db
from ..model.brew_session import BrewSession
from ..model.brew_session_step import BrewSessionStep
from ..model.brew_plant import BrewPlant


def _decimal(value):
    return None if value is None else str(Decimal(str(value)))


def build_session_report_data(session_id, *, plant_id):
    """Exige planta explícita; sessão de outra planta retorna 404.

    recipe_id é apenas identificação: não é snapshot histórico da receita.
    Os passos são os registros próprios da sessão no instante da leitura.
    """
    with db.session.no_autoflush:
        if not current_user.is_authenticated:
            abort(401)
        if not all(current_user.has_permission(p) for p in ('brew_sessions.list', 'brew_plants.list', 'brew_session_steps.list')):
            abort(403)
    if type(session_id) is not int or type(plant_id) is not int or min(session_id, plant_id) < 1:
        abort(400)
    with db.session.session_factory() as reader:
        if reader.query(BrewPlant.id).filter_by(id=plant_id, is_deleted=False).first() is None:
            abort(404)
        session = reader.query(BrewSession).filter_by(id=session_id, plant_id=plant_id, is_deleted=False).first()
        if session is None:
            abort(404)
        steps = (reader.query(BrewSessionStep).filter_by(session_id=session.id, is_deleted=False)
                 .order_by(BrewSessionStep.step_index, BrewSessionStep.id).limit(2001).all())
        if len(steps) > 2000:
            abort(413)
        record = {key: getattr(session, key) for key in
                  ('id', 'name', 'plant_id', 'recipe_id', 'status', 'current_step_index', 'notes')}
        for key in ('started_at', 'completed_at', 'paused_at', 'insumos_baixados_em'):
            value = getattr(session, key)
            record[key] = value.isoformat() if value else None
        for key in ('custo_total_insumos', 'volume_real_litros'):
            record[key] = _decimal(getattr(session, key))
        items = [{
            'id': step.id, 'step_index': step.step_index, 'name': step.name,
            'step_type': step.step_type, 'status': step.status,
            'target_temp': _decimal(step.target_temp),
            'duration_seconds': step.duration_seconds, 'actual_duration_s': step.actual_duration_s,
            'started_at': step.started_at.isoformat() if step.started_at else None,
            'completed_at': step.completed_at.isoformat() if step.completed_at else None,
        } for step in steps]
    return {'contract': 'brewstation.session.v1', 'session': record, 'steps': items}


def generate_session_report(template_key, session_id, *, plant_id, version=None, parameters=None, format='html'):
    """Integração opcional; aplica permissões de domínio e de Reports."""
    data = build_session_report_data(session_id, plant_id=plant_id)
    from addons.addon_reports.root.services.report_template_service import generate_report
    return generate_report(template_key, version=version, data=data, parameters=parameters, format=format)
