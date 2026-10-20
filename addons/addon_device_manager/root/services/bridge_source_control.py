"""Versioned leased source contract; reports logical output, never flame feedback."""
from copy import deepcopy
from datetime import datetime, timezone
import math
from .bridge_heating_telemetry import utc


def validate(value, device_id, received_at, previous=None, retained=False):
    if retained or not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] != 1:
        raise ValueError('Contrato de fonte inválido/retido.')
    if value.get('device_id') != device_id or value.get('backend') not in ('real','simulated'):
        raise ValueError('Identidade/origem inválida.')
    now, observed = utc(received_at), utc(value.get('observed_at'))
    if not -2 <= (now-observed).total_seconds() <= 5:
        raise ValueError('Telemetria antiga.')
    for key in ('boot_id','arm_token'):
        if not isinstance(value.get(key), str) or not 1 <= len(value[key]) <= 64:
            raise ValueError('Boot/token inválido.')
    seq = value.get('sequence')
    if type(seq) is not int or seq < 1:
        raise ValueError('Sequência inválida.')
    if previous and (observed < utc(previous['observed_at']) or
        (value['boot_id'] == previous['boot_id'] and seq <= previous['sequence']) or
        (value['boot_id'] != previous['boot_id'] and observed <= utc(previous['observed_at']))):
        raise ValueError('Mensagem repetida/fora de ordem.')
    if value.get('participation') not in ('primary','auxiliary') or value.get('external_protection') != 'independent_hardware':
        raise ValueError('Fonte sem contrato de proteção externa.')
    if not isinstance(value.get('temperature_sensor'), str) or not value['temperature_sensor']:
        raise ValueError('Sensor da fonte obrigatório.')
    temp = value.get('temperature')
    if temp is not None and (type(temp) not in (int,float) or not math.isfinite(temp) or not -55 <= temp <= 150):
        raise ValueError('Temperatura inválida.')
    if type(value.get('armed')) is not bool or type(value.get('output_on')) is not bool:
        raise ValueError('Estado lógico inválido.')
    lease = value.get('lease_id')
    if (lease is not None and (not isinstance(lease,str) or not 1 <= len(lease) <= 64)) or value['armed'] != (lease is not None):
        raise ValueError('Autorização inválida.')
    target = value.get('target')
    if target is not None and (type(target) not in (int,float) or not math.isfinite(target) or not 1 <= target <= 110):
        raise ValueError('Alvo inválido.')
    if value['output_on'] and not value['armed']:
        raise ValueError('Saída ligada sem autorização.')
    for key in ('reason','fault'):
        if value.get(key) is not None and (not isinstance(value[key],str) or len(value[key]) > 1000):
            raise ValueError('Mensagem inválida.')
    keys = ('version','device_id','boot_id','arm_token','sequence','backend','participation','armed',
            'lease_id','output_on','target','reason','fault','external_protection','limits',
            'temperature_sensor','temperature','controller_device')
    return {**{key:deepcopy(value.get(key)) for key in keys}, 'observed_at':observed.isoformat(),
            'received_at':now.isoformat(), 'source':'bridge_source_v1'}


def fresh(value, now=None):
    if not value or value.get('source') != 'bridge_source_v1':
        return False
    try:
        now = utc(now or datetime.now(timezone.utc))
        return 0 <= (now-utc(value['received_at'])).total_seconds() <= 5 and -2 <= (now-utc(value['observed_at'])).total_seconds() <= 5
    except (ValueError, TypeError, KeyError):
        return False
