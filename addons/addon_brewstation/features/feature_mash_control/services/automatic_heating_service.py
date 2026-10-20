"""Explicit, process-local leases renewed by observations, never dashboard polling.

Run the HTTP endpoints and MQTT receiver in the same application process. A worker
without the lease cannot renew it. Restart/timeout/pause never rearms automatically.
"""
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4
import logging
from flask import current_app, url_for, has_request_context
from core.db import db
from core.event_bus import event_bus
from addons.addon_device_manager.root.services import device_service
from addons.addon_device_manager.root.services.bridge_source_control import fresh
from ..model.brew_session import BrewSession
from ..model.brew_session_step import BrewSessionStep
from ..model.brew_plant_vessel import BrewPlantVessel
from . import heating_configuration_service as config

logger = logging.getLogger(__name__)
_lock = RLock()
_registered = False


def leases():
    return current_app.extensions.setdefault('automatic_heating_leases', {})


def actor(source):
    function = source.get('device_function_name')
    return device_service.find_unique_actor_external_id_by_function_name(function) if function else None


def source_for(vessel, source_id):
    return next((s for s in config.config(vessel)['sources'] if s['id'] == source_id), None)


def facts(vessel, source):
    if not source or not source['enabled'] or source['mode'] != 'automatic' or vessel.is_deleted:
        raise config.HeatingError('Fonte automática indisponível.', 409)
    from ..model.brew_plant import BrewPlant
    plant = db.session.get(BrewPlant, vessel.plant_id)
    if not plant or plant.is_deleted:
        raise config.HeatingError('Planta indisponível.', 409)
    if source['device_function_name'] not in {m.device_function_name for m in config.mappings(vessel)}:
        raise config.HeatingError('Mapeamento da fonte removido.', 409)
    identifier = actor(source)
    frame = device_service.get_source_telemetry(identifier) if identifier else None
    if not fresh(frame) or frame.get('fault') or frame['participation'] != source['role']:
        raise config.HeatingError('Bridge sem telemetria fresca/compatível da fonte protegida.', 409)
    sessions = BrewSession.query.filter_by(plant_id=vessel.plant_id, is_deleted=False).filter(BrewSession.status.in_(('active','paused'))).all()
    if len(sessions) != 1 or sessions[0].status != 'active':
        raise config.HeatingError('Exige uma única sessão ativa.', 409)
    session = sessions[0]
    cfg = config.config(vessel)
    target = cfg['target_temp']
    step_id = None
    if cfg['usage'] == 'process':
        steps = BrewSessionStep.query.filter_by(session_id=session.id, vessel_id=vessel.id, status='active', is_deleted=False).all()
        if len(steps) != 1:
            raise config.HeatingError('Exige etapa ativa deste tanque.', 409)
        target, step_id = steps[0].target_temp, steps[0].id
    if type(target) not in (int,float) or not 1 <= target <= 110:
        raise config.HeatingError('Alvo de aquecimento inválido.', 409)
    from .heating_request_service import observation, utcnow
    sensor = config.primary_sensor(vessel)
    temperature = observation(sensor, utcnow(), 5, -55, 150)
    if temperature is None:
        raise config.HeatingError('Temperatura recebida ausente ou antiga.', 409)
    if not sensor or frame['temperature_sensor'] != sensor.device_function_name or frame.get('temperature') is None or abs(frame['temperature']-temperature['value']) > 0.5:
        raise config.HeatingError('Sensor/temperatura do Bridge diverge do tanque.', 409)
    if source['role'] == 'auxiliary':
        from .heating_telemetry_service import read
        controller = read(vessel, max_age=5)
        if (not controller.get('fresh') or controller.get('device_id') != frame.get('controller_device')
                or controller.get('backend') != frame['backend'] or controller.get('owner') != 'local_recipe'
                or controller.get('fault') or controller.get('target') is None or abs(controller['target']-target) > 0.1):
            raise config.HeatingError('Auxiliar exige PID local compatível, fresco e no mesmo alvo.', 409)
    return identifier, frame, target, (session.id, step_id, vessel.heating_version, frame['backend'])


def _url(vessel, source):
    values = dict(plant_id=vessel.plant_id, vessel_id=vessel.id, source_id=source['id'])
    if has_request_context():
        return url_for('heating_workspace.automatic', **values)
    return current_app.url_map.bind('').build('heating_workspace.automatic', values)


def view(vessel, source):
    if source['mode'] != 'automatic':
        return None
    frame = device_service.get_source_telemetry(actor(source)) or {}
    valid = fresh(frame)
    reason = frame.get('reason', 'Aguardando telemetria da fonte protegida')
    can_arm = False
    try:
        facts(vessel, source)
        can_arm = not frame.get('armed')
    except config.HeatingError as exc:
        reason = str(exc)
    if frame.get('fault'):
        reason = frame['fault'] + ' · ' + reason
    return {'fresh': valid, 'armed': bool(valid and frame.get('armed')),
            'output_on': frame.get('output_on') if valid else None,
            'backend': frame.get('backend'), 'target': frame.get('target'), 'fault': frame.get('fault'),
            'reason': reason, 'can_arm': can_arm, 'control_url': _url(vessel, source),
            'physical_state_confirmed': False}


def _send(identifier, frame, entry, action):
    entry['sequence'] += 1
    command = {'version':1, 'action':action, 'boot_id':frame['boot_id'],
        'arm_token':frame['arm_token'], 'lease_id':entry['lease_id'], 'sequence':entry['sequence'],
        'issued_at':datetime.now(timezone.utc).isoformat(), 'target':entry['target'], 'limits':entry['limits']}
    if not device_service.send_source_command(identifier, command):
        raise config.HeatingError('MQTT indisponível; autorização não enviada.', 503)


def control(vessel, source_id, action, user_id):
    source = source_for(vessel, source_id)
    if source is None:
        raise config.HeatingError('Fonte deste tanque não encontrada.', 404)
    with _lock:
        key = (vessel.id, source_id)
        if action == 'stop':
            leases().pop(key, None)
            identifier = actor(source)
            if identifier:
                device_service.send_source_command(identifier, {'action':'stop'})
            logger.warning('Parada de fonte solicitada: tanque=%s fonte=%s operador=%s', vessel.id, source_id, user_id)
            # A failed network OFF is not a confirmation; the lease still expires locally.
            return 'Renovação interrompida e OFF solicitado. Sem comunicação, o Bridge desabilita ao expirar a autorização (10 s mais um ciclo do loop).'
        if action != 'arm':
            raise config.HeatingError('Ação inválida.')
        identifier, frame, target, context = facts(vessel, source)
        if frame['armed'] or key in leases():
            raise config.HeatingError('Fonte já habilitada; pare antes de habilitar novamente.', 409)
        # A physical output cannot be shared between independently armed vessels.
        if any(e['identifier'] == identifier for e in leases().values()):
            raise config.HeatingError('Fonte já autorizada em outro tanque.', 409)
        entry = {'identifier':identifier, 'lease_id':str(uuid4()), 'sequence':0, 'target':target,
                 'limits':source['automatic_limits'], 'context':context, 'boot_id':frame['boot_id'],
                 'arm_token':frame['arm_token'], 'started_at':datetime.now(timezone.utc), 'user_id':user_id}
        _send(identifier, frame, entry, 'arm')
        leases()[key] = entry
        logger.warning('Habilitação de fonte solicitada: tanque=%s fonte=%s operador=%s backend=%s', vessel.id, source_id, user_id, frame['backend'])
        return 'Habilitação enviada. Aguarde confirmação lógica do Bridge; não confirma chama nem abertura física.'


def on_observation(function_name=None):
    if not function_name:
        return
    with _lock:
        for key, entry in list(leases().items()):
            vessel = db.session.get(BrewPlantVessel, key[0])
            source = source_for(vessel, key[1]) if vessel else None
            # Source state publications drive renewal; unrelated sensors never renew leases.
            if not source:
                leases().pop(key, None)
                device_service.send_source_command(entry['identifier'], {'action':'stop'})
                continue
            if source.get('device_function_name') != function_name:
                continue
            try:
                identifier, frame, target, context = facts(vessel, source)
                if (identifier != entry['identifier'] or context != entry['context']
                        or target != entry['target'] or frame['boot_id'] != entry['boot_id']):
                    raise config.HeatingError('Contexto alterado; habilite novamente.')
                if not frame['armed']:
                    initial = frame['arm_token'] == entry['arm_token'] and (datetime.now(timezone.utc)-entry['started_at']).total_seconds() < 3
                    if initial:
                        continue
                    raise config.HeatingError('Fonte desabilitada no Bridge; habilite novamente.')
                if frame['lease_id'] != entry['lease_id']:
                    raise config.HeatingError('Autorização divergente.')
                _send(identifier, frame, entry, 'renew')
            except Exception:
                db.session.rollback()
                leases().pop(key, None)
                device_service.send_source_command(entry['identifier'], {'action':'stop'})
                logger.exception('Renovação interrompida para a fonte %s', key)


def reconcile_plant(plant_id):
    with _lock:
        for key in list(leases()):
            vessel = db.session.get(BrewPlantVessel, key[0])
            if vessel and vessel.plant_id == plant_id:
                source = source_for(vessel, key[1])
                if source:
                    on_observation(source.get('device_function_name'))


def register(app):
    global _registered
    app.extensions['automatic_heating_leases'] = {}
    if not _registered:
        event_bus.subscribe('device_manager.actor.observation_received', on_observation)
        _registered = True
