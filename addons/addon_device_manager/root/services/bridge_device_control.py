"""Explicit Bridge control contract, separate from optimistic legacy value caches."""
from copy import deepcopy
from datetime import datetime, timezone
import math
from .bridge_heating_telemetry import utc

ACTIONS = {'power': {'power_prepare', 'power_enable', 'power_release', 'power_off'},
           'pump': {'pump_set', 'pump_release', 'pump_confirm', 'pump_decline'}}


def validate(value, device_id, received_at, previous=None, retained=False):
    if retained or not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] != 1:
        raise ValueError('Contrato de controle inválido ou retido.')
    if value.get('device_id') != device_id or value.get('kind') not in ACTIONS:
        raise ValueError('Dispositivo/tipo inválido.')
    if not isinstance(value.get('boot_id'), str) or not 1 <= len(value['boot_id']) <= 64:
        raise ValueError('Boot inválido.')
    if type(value.get('sequence')) is not int or value['sequence'] < 1:
        raise ValueError('Sequência inválida.')
    observed, now = utc(value.get('observed_at')), utc(received_at)
    if not -2 <= (now-observed).total_seconds() <= 5:
        raise ValueError('Telemetria de controle expirada.')
    if previous and ((value['boot_id'] == previous['boot_id'] and value['sequence'] <= previous['sequence']) or observed <= utc(previous['observed_at'])):
        raise ValueError('Telemetria repetida ou fora de ordem.')
    if value.get('external_policy') not in ('manual_override', 'local_only') or value.get('backend') not in ('real', 'simulated'):
        raise ValueError('Política/backend inválido.')
    if value.get('owner') not in ('local_recipe', 'local_manual', 'remote_manual', 'failsafe', 'idle', 'manual', 'automatic'):
        raise ValueError('Controle inválido.')
    for key in ('output_on', 'manual_enabled', 'pending_confirmation'):
        if type(value.get(key)) is not bool:
            raise ValueError('Estado inválido.')
    percent = value.get('manual_percent')
    if percent is not None and (type(percent) not in (int, float) or not math.isfinite(percent) or not 0 <= percent <= 100):
        raise ValueError('Potência inválida.')
    fault = value.get('fault')
    if fault is not None and (not isinstance(fault, str) or len(fault) > 1000):
        raise ValueError('Falha inválida.')
    result = value.get('last_command')
    if result is not None and (not isinstance(result, dict) or result.get('status') not in ('applied', 'rejected') or any(not isinstance(result.get(k), str) or len(result[k]) > limit for k, limit in [('request_id',64),('action',40),('message',250)])):
        raise ValueError('Resultado inválido.')
    clean = {key: deepcopy(value.get(key)) for key in ('version','device_id','boot_id','sequence','observed_at','backend','kind','external_policy','output_on','manual_enabled','manual_percent','owner','fault','pending_confirmation','last_command')}
    clean['received_at'] = now.isoformat()
    return clean


def fresh(value, now=None):
    try:
        now = utc(now or datetime.now(timezone.utc))
        return bool(value and -2 <= (now-utc(value['observed_at'])).total_seconds() <= 5 and 0 <= (now-utc(value['received_at'])).total_seconds() <= 5)
    except (KeyError, ValueError, TypeError):
        return False


def command(telemetry, action, value=None):
    from uuid import uuid4
    if not fresh(telemetry):
        raise ValueError('Aguarde telemetria recente do Bridge (até 5 s).')
    if not isinstance(action, str) or action not in ACTIONS[telemetry['kind']]:
        raise ValueError('Operação incompatível com este equipamento.')
    if telemetry['external_policy'] == 'local_only' and action != 'power_off':
        raise ValueError('Política local_only: apenas desligamento remoto permitido.')
    if telemetry.get('fault') and action not in ('power_off', 'pump_set'):
        raise ValueError('Bridge em falha; verifique o equipamento local.')
    if action == 'power_prepare' and (type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= 100):
        raise ValueError('Informe potência de 0 a 100%.')
    if action == 'pump_set' and (type(value) is not bool or (telemetry.get('fault') and value)):
        raise ValueError('Estado da bomba inválido ou Bridge em falha.')
    if action in ('pump_confirm','pump_decline') and not telemetry['pending_confirmation']:
        raise ValueError('Não há confirmação de bomba pendente.')
    return {'version':1, 'request_id':str(uuid4()), 'boot_id':telemetry['boot_id'],
            'issued_at':datetime.now(timezone.utc).isoformat(), 'action':action, 'value':value}
