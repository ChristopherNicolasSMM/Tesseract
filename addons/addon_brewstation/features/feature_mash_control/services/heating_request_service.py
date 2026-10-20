"""Server-side advisory rules. No path in this module commands an actuator."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import logging
import math

from flask import current_app, url_for, has_request_context
from sqlalchemy import update
from core.db import db
from core.event_bus import event_bus
from core.task_registry import register_task
from addons.addon_device_manager.root.services import device_service
from addons.addon_device_manager.root.services.device_function_lookup import get_function_by_name
from ..model.brew_plant import BrewPlant
from ..model.brew_plant_vessel import BrewPlantVessel
from ..model.brew_session import BrewSession
from ..model.brew_session_step import BrewSessionStep
from ..model.heating_request import HeatingRequest
from . import heating_configuration_service as configuration

logger = logging.getLogger(__name__)
_registered = False
DEFAULTS = {"enabled": False, "source_id": None, "demand_mapping_id": None,
            "require_demand": True, "demand_source": "sensor", "demand_threshold": 80.0, "demand_hysteresis": 10.0,
            "minimum_gap": 2.0, "gap_hysteresis": 0.5, "minimum_seconds": 10.0,
            "cooldown_seconds": 60.0, "validity_seconds": 120.0, "max_age_seconds": 15.0}
ACTIVE_STATES = ("requested", "acknowledged")
LABELS = {"requested": "Solicitação pendente", "acknowledged": "Ação declarada pelo operador",
          "declined": "Recusada pelo operador", "completed": "Concluída pelo operador",
          "cancelled": "Solicitação cancelada; revise manualmente a fonte"}


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def rule(vessel):
    return {**DEFAULTS, **deepcopy(configuration.config(vessel).get("rule") or {})}


def demand_options(vessel):
    return [m for m in configuration.mappings(vessel)
            if (meta := get_function_by_name(m.device_function_name))
            and meta.get("category") == "sensor" and meta.get("data_type") in ("float", "int")
            and meta.get("unit") in ("%", "percent")]


def save_rule(vessel, data):
    selected = str(data.get("source_id") or "")
    sources = configuration.config(vessel)["sources"]
    enabled = data.get("enabled") in (True, "on", "true")
    if selected and not any(s['id'] == selected and s['enabled'] and s['mode'] == 'advisory' for s in sources):
        raise configuration.HeatingError("Escolha fonte disponível em modo solicitação deste tanque.")
    if enabled and not selected:
        raise configuration.HeatingError("Selecione a fonte da solicitação.")
    value = {"enabled": enabled, "source_id": selected or None,
             "require_demand": data.get("require_demand") in (True, "on", "true")}
    mapping_id = data.get("demand_mapping_id")
    if isinstance(mapping_id, bool) or not isinstance(mapping_id, (str, int, type(None))):
        raise configuration.HeatingError("Sensor de demanda inválido.")
    try:
        mapping_id = int(mapping_id) if mapping_id not in (None, "") else None
    except ValueError:
        raise configuration.HeatingError("Sensor de demanda inválido.") from None
    if mapping_id is not None and mapping_id not in {m.id for m in demand_options(vessel)}:
        raise configuration.HeatingError("Demanda exige sensor percentual deste tanque, não atuador/comando.")
    value['demand_mapping_id'] = mapping_id
    value['demand_source'] = configuration._enum(data.get('demand_source', 'sensor'), ('sensor','bridge'), 'Origem da demanda')
    if enabled and value['require_demand'] and value['demand_source'] == 'bridge':
        from .heating_telemetry_service import controller_options
        if configuration.config(vessel).get('controller_mapping_id') not in {m.id for m in controller_options(vessel)}:
            raise configuration.HeatingError('Selecione o controlador Bridge na preparação do tanque.')
    bounds = {"demand_threshold": (0, 100), "demand_hysteresis": (0, 100),
              "minimum_gap": (0.1, 50), "gap_hysteresis": (0.1, 50),
              "minimum_seconds": (1, 3600), "cooldown_seconds": (1, 86400),
              "validity_seconds": (5, 3600), "max_age_seconds": (1, 300)}
    for key, limits in bounds.items():
        value[key] = configuration._number(data.get(key, DEFAULTS[key]), key, *limits)
        if value[key] is None:
            raise configuration.HeatingError("Preencha todos os limites da regra.")
    if value['gap_hysteresis'] >= value['minimum_gap']:
        raise configuration.HeatingError("Histerese de temperatura deve ser menor que a distância do alvo.")
    if value['demand_hysteresis'] > value['demand_threshold']:
        raise configuration.HeatingError("Histerese de demanda deve ser menor ou igual ao limite.")
    cfg = configuration.config(vessel)
    cfg['rule'] = value
    return configuration._save(vessel, cfg, data.get('expected_version'))


def observation(mapping, now, max_age, low, high):
    if mapping is None:
        return None
    identifier = device_service.find_unique_actor_external_id_by_function_name(mapping.device_function_name)
    observed = device_service.get_observation(identifier) if identifier else None
    if not observed or observed.get('source') != 'mqtt_state':
        return None
    number = observed.get('value')
    if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not low <= number <= high:
        return None
    try:
        age = (now - aware(observed['observed_at'])).total_seconds()
    except (KeyError, ValueError, TypeError, AttributeError):
        return None
    return observed if 0 <= age <= max_age else None


def facts(vessel, now):
    cfg, settings = configuration.config(vessel), rule(vessel)
    base = {"valid": False, "reason": "Regra desabilitada", "settings": settings}
    if not settings['enabled']:
        return base
    source = next((s for s in cfg['sources'] if s['id'] == settings['source_id'] and s['enabled'] and s['mode'] == 'advisory'), None)
    if not source:
        return {**base, "reason": "Fonte indisponível ou fora do modo solicitação"}
    plant = db.session.get(BrewPlant, vessel.plant_id)
    if vessel.is_deleted or not plant or plant.is_deleted:
        return {**base, "reason": "Planta ou tanque indisponível"}
    sessions = BrewSession.query.filter_by(plant_id=vessel.plant_id, is_deleted=False).filter(BrewSession.status.in_(['active','paused'])).all()
    if len(sessions) != 1 or sessions[0].status != 'active':
        return {**base, "reason": "Exige uma única sessão ativa e não pausada"}
    session = sessions[0]
    step_id, target = None, cfg['target_temp']
    if cfg['usage'] == 'process':
        steps = BrewSessionStep.query.filter_by(session_id=session.id, vessel_id=vessel.id, status='active', is_deleted=False).all()
        if len(steps) != 1:
            return {**base, "reason": "Exige uma etapa ativa deste tanque"}
        step_id, target = steps[0].id, steps[0].target_temp
    if isinstance(target, bool) or not isinstance(target, (int,float)) or not math.isfinite(target) or not 0 <= target <= 110:
        return {**base, "reason": "Alvo válido não disponível"}
    temp = observation(configuration.primary_sensor(vessel), now, settings['max_age_seconds'], 0, 110)
    if not temp:
        return {**base, "reason": "Temperatura recebida ausente, antiga ou inválida"}
    demand, bridge_boot = None, None
    if settings['require_demand']:
        if settings['demand_source'] == 'bridge':
            from .heating_telemetry_service import read
            telemetry = read(vessel, now, settings['max_age_seconds'])
            if (not telemetry['fresh'] or telemetry.get('backend') != 'real'
                    or telemetry.get('owner') != 'local_recipe' or telemetry.get('fault')
                    or telemetry.get('demand_percent') is None
                    or telemetry.get('target') is None or abs(telemetry['target']-target) > 0.1
                    or telemetry.get('temperature') is None or abs(telemetry['temperature']-temp['value']) > 0.5):
                return {**base, 'reason':'Bridge sem receita local real/fresca compatível com o alvo e sensor deste tanque'}
            demand, bridge_boot = {'value':telemetry['demand_percent']}, telemetry['boot_id']
        else:
            mapping = next((m for m in demand_options(vessel) if m.id == settings['demand_mapping_id']), None)
            demand = observation(mapping, now, settings['max_age_seconds'], 0, 100)
            if not demand:
                return {**base, "reason": "Demanda percentual recebida ausente, antiga ou inválida"}
    gap = target - temp['value']
    enters = gap >= settings['minimum_gap'] and (demand is None or demand['value'] > settings['demand_threshold'])
    exits = gap <= settings['minimum_gap'] - settings['gap_hysteresis'] or (demand is not None and demand['value'] <= settings['demand_threshold'] - settings['demand_hysteresis'])
    return {**base, "valid": True, "reason": "Condição atendida" if enters else "Aguardando condição",
            "source": source, "session_id": session.id, "step_id": step_id, "target": target,
            "temperature": temp['value'], "demand": demand['value'] if demand else None,
            "context": [session.id, step_id, target, vessel.heating_version, source['id']] + ([bridge_boot] if bridge_boot else []),
            "enters": enters, "exits": exits}


def _started_at():
    return aware(current_app.config.setdefault('HEATING_RUNTIME_STARTED_AT', utcnow().isoformat()))


def _cancel(request, reason, now):
    if request and request.status in ACTIVE_STATES:
        request.status, request.reason, request.updated_at = 'cancelled', reason[:255], now


def evaluate(vessel_id, now=None, *, commit=True):
    now = aware(now or utcnow())
    vessel = db.session.get(BrewPlantVessel, vessel_id)
    if not vessel:
        return
    # Shared lock with configuration/workspace maintenance. Refresh AFTER acquiring it.
    db.session.execute(update(BrewPlant).where(BrewPlant.id == vessel.plant_id).values(updated_at=BrewPlant.updated_at))
    db.session.refresh(vessel)
    state = deepcopy(vessel.heating_runtime_json or {})
    current = HeatingRequest.query.filter_by(vessel_id=vessel.id).filter(HeatingRequest.status.in_(ACTIVE_STATES)).all()
    data = facts(vessel, now)
    if not data['settings']['enabled']:
        for request in current:
            _cancel(request, 'Regra desabilitada', now)
        vessel.heating_runtime_json = None
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return
    started = _started_at()
    restarted = not state.get('last_evaluated_at') or aware(state['last_evaluated_at']) < started
    changed_context = restarted or state.get('context') != data.get('context')
    expired = False
    for request in current:
        if not data['valid'] or changed_context or aware(request.created_at) < started:
            _cancel(request, data['reason'] if not data['valid'] else 'Contexto alterado ou servidor reiniciado', now)
        elif request.status == 'requested' and now >= aware(request.expires_at):
            _cancel(request, 'Prazo de resposta expirado', now)
            expired = True
        elif data['exits']:
            _cancel(request, 'Condição de aquecimento encerrada', now)
    if changed_context or not data['valid'] or data.get('exits'):
        state = {"last_request_at": state.get('last_request_at')}
    state.update(context=data.get('context'), reason=data['reason'], evaluated_at=now.isoformat())
    if expired:
        state['latched'] = True
    if data['valid'] and data['enters'] and not state.get('latched'):
        previous = state.get('last_evaluated_at')
        if previous and (now - aware(previous)).total_seconds() > data['settings']['max_age_seconds']:
            state.pop('candidate_since', None)
        state.setdefault('candidate_since', now.isoformat())
        cooldown = state.get('last_request_at')
        ready = (now-aware(state['candidate_since'])).total_seconds() >= data['settings']['minimum_seconds']
        ready = ready and (not cooldown or (now-aware(cooldown)).total_seconds() >= data['settings']['cooldown_seconds'])
        if ready:
            request = HeatingRequest(vessel_id=vessel.id, session_id=data['session_id'], source_id=data['source']['id'],
                status='requested', created_at=now, updated_at=now,
                expires_at=now+timedelta(seconds=data['settings']['validity_seconds']),
                context_json={"settings": data['settings'], "context": data['context'], "source_name": data['source']['name'],
                              "temperature": data['temperature'], "target": data['target'], "demand_percent": data['demand'],
                              "source": deepcopy(data['source']), "vessel_name": vessel.label_text, "plant_id": vessel.plant_id})
            db.session.add(request)
            state.update(latched=True, last_request_at=now.isoformat(), reason='Solicitação emitida')
    elif not data['valid'] or not data.get('enters'):
        state.pop('candidate_since', None)
    state['last_evaluated_at'] = now.isoformat()
    vessel.heating_runtime_json = state
    if commit:
        db.session.commit()
    else:
        db.session.flush()


def respond(vessel, request_id, action, user_id, now=None):
    now = aware(now or utcnow())
    if action not in ('acknowledge', 'decline', 'complete'):
        raise configuration.HeatingError('Resposta inválida.')
    # Revalidate live context before accepting any response; also closes stale requests.
    evaluate(vessel.id, now, commit=False)
    request = HeatingRequest.query.filter_by(id=request_id, vessel_id=vessel.id).first()
    if not request:
        raise configuration.HeatingError('Solicitação deste tanque não encontrada.', 404)
    required = 'acknowledged' if action == 'complete' else 'requested'
    if request.status != required:
        db.session.commit()  # Keep cancellations discovered by revalidation.
        raise configuration.HeatingError('Solicitação alterada, encerrada ou expirada. Atualize o painel.', 409)
    status = {'acknowledge':'acknowledged', 'decline':'declined', 'complete':'completed'}[action]
    context = deepcopy(request.context_json)
    context.setdefault('responses', []).append({'action': action, 'user_id': user_id, 'at': now.isoformat()})
    # Compare-and-swap also protects competing responses across workers.
    result = db.session.execute(update(HeatingRequest).where(HeatingRequest.id == request.id,
        HeatingRequest.vessel_id == vessel.id, HeatingRequest.status == required).values(
        status=status, responded_at=now, responded_by=user_id, updated_at=now, context_json=context,
        reason='Declaração do operador; nenhum comando físico enviado'))
    if result.rowcount != 1:
        raise configuration.HeatingError('Outra resposta foi registrada. Atualize o painel.', 409)
    db.session.commit()


def response_url(vessel, request):
    values = dict(plant_id=vessel.plant_id, vessel_id=vessel.id, request_id=request.id)
    if has_request_context():
        return url_for('heating_workspace.respond', **values)
    return current_app.url_map.bind('', script_name=current_app.config.get('APPLICATION_ROOT', '/')).build('heating_workspace.respond', values)


def view(vessel, selected_session=None):
    now = utcnow()
    data, state = facts(vessel, now), vessel.heating_runtime_json or {}
    requests = HeatingRequest.query.filter_by(vessel_id=vessel.id).order_by(HeatingRequest.id.desc()).limit(5).all()
    history = []
    for request in requests:
        live = (data['valid'] and aware(request.created_at) >= _started_at() and state.get('context') == data.get('context')
                and request.context_json.get('context') == data.get('context') and not data.get('exits')
                and (selected_session is None or selected_session.id == request.session_id))
        live = live and (request.status != 'requested' or now < aware(request.expires_at))
        history.append({"id": request.id, "status": request.status, "status_label": LABELS[request.status],
            "source_name": request.context_json.get('source_name'), "reason": request.reason,
            "created_at": aware(request.created_at).isoformat(), "expires_at": aware(request.expires_at).isoformat(),
            "responded_by": request.responded_by, "responded_at": aware(request.responded_at).isoformat() if request.responded_at else None,
            "can_respond": bool(live and request.status == 'requested'),
            "can_complete": bool(live and request.status == 'acknowledged'),
            "currently_valid": bool(live), "responses": request.context_json.get("responses", []),
            "response_url": response_url(vessel, request)})
    return {"enabled": rule(vessel)['enabled'], "status": data['reason'],
            "automatic_demand_percent": data.get('demand'), "requests": history}


def reconcile_plant(plant_id):
    """Lifecycle reconciliation; failures never undo an already committed session action."""
    from .automatic_heating_service import reconcile_plant as reconcile_automatic
    try:
        reconcile_automatic(plant_id)
    except Exception:
        db.session.rollback()
        logger.exception('Falha ao reconciliar fontes automáticas da planta %s', plant_id)
    ids = [v.id for v in BrewPlantVessel.query.filter_by(plant_id=plant_id).all()
           if rule(v)['enabled'] or v.heating_runtime_json]
    for vessel_id in ids:
        try:
            evaluate(vessel_id)
        except Exception:
            db.session.rollback()
            logger.exception('Falha ao reconciliar aquecimento do tanque %s', vessel_id)


def sweep():
    ids = [row.id for row in BrewPlantVessel.query.all()
           if rule(row)['enabled'] or row.heating_runtime_json]
    for vessel_id in ids:
        try:
            evaluate(vessel_id)
        except Exception:
            db.session.rollback()
            logger.exception('Falha ao avaliar solicitação de aquecimento do tanque %s', vessel_id)
    return len(ids)


def on_observation(function_name=None):
    if not function_name:
        return
    vessel_ids = {mapping.vessel_id for mapping in configuration.BrewPlantMapping.query.filter_by(
        device_function_name=function_name, is_deleted=False).all()}
    for vessel_id in vessel_ids:
        vessel = db.session.get(BrewPlantVessel, vessel_id)
        if vessel and (rule(vessel)['enabled'] or vessel.heating_runtime_json):
            try:
                evaluate(vessel_id)
            except Exception:
                db.session.rollback()
                logger.exception('Erro na regra de aquecimento do tanque %s', vessel_id)


def register(app):
    global _registered
    app.config['HEATING_RUNTIME_STARTED_AT'] = utcnow().isoformat()
    if not _registered:
        event_bus.subscribe('device_manager.actor.observation_received', on_observation)
        _registered = True
    register_task('brewstation.evaluate_heating_requests', sweep)
