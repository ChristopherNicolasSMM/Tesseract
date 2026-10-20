"""Version 1 Bridge telemetry validation. A GPIO report is not electrical feedback."""
from copy import deepcopy
from datetime import datetime, timezone
import math

OWNERS = {'local_recipe', 'local_manual', 'remote_manual', 'failsafe', 'idle'}


def utc(value):
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.tzinfo is None:
        raise ValueError('Data UTC com fuso obrigatória.')
    return parsed.astimezone(timezone.utc)


def validate(value, device_id, received_at, previous=None, retained=False):
    if retained or not isinstance(value, dict) or type(value.get('version')) is not int or value.get('version') != 1:
        raise ValueError('Telemetria não suportada ou retida.')
    if value.get('device_id') != device_id:
        raise ValueError('Identificação não corresponde à função do dispositivo.')
    boot, sequence = value.get('boot_id'), value.get('sequence')
    if not isinstance(boot, str) or not 1 <= len(boot) <= 64 or isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise ValueError('Boot/sequência inválidos.')
    observed = utc(value.get('observed_at'))
    now = utc(received_at)
    if not -2 <= (now-observed).total_seconds() <= 120:
        raise ValueError('Horário de telemetria fora da tolerância de transporte.')
    if previous:
        same_boot = previous['boot_id'] == boot
        if ((same_boot and sequence <= previous['sequence']) or observed < utc(previous['observed_at'])
                or (not same_boot and observed <= utc(previous['observed_at']))):
            raise ValueError('Mensagem repetida ou fora de ordem.')
    if value.get('backend') not in ('real', 'simulated') or not isinstance(value.get('owner'), str) or value.get('owner') not in OWNERS:
        raise ValueError('Origem/controle inválidos.')
    if value.get('external_policy') not in ('manual_override', 'local_only') or not isinstance(value.get('output_on'), bool):
        raise ValueError('Política/saída inválida.')
    if value.get('fault') is not None and (not isinstance(value['fault'], str) or len(value['fault']) > 1000):
        raise ValueError('Falha inválida.')
    for key, low, high, optional in (
        ('demand_percent',0,100,True), ('power_limit_percent',0,100,True), ('automatic_percent',0,100,True),
        ('selected_percent',0,100,False), ('applied_window_percent',0,100,False),
        ('window_seconds',0.001,3600,False), ('temperature',-55,150,True), ('target',0,110,True)):
        number = value.get(key)
        if number is None and optional:
            continue
        if isinstance(number, bool) or not isinstance(number,(int,float)) or not math.isfinite(number) or not low <= number <= high:
            raise ValueError('Métrica inválida: '+key)
    keys = {'version','device_id','boot_id','sequence','observed_at','backend','owner','external_policy',
            'output_on','fault','demand_percent','power_limit_percent','automatic_percent','selected_percent',
            'applied_window_percent','window_seconds','temperature','target'}
    result = {key: deepcopy(value.get(key)) for key in keys}
    result.update(received_at=now.isoformat(), observed_at=observed.isoformat(), source='bridge_heating_v1')
    return result


def fresh(value, now, max_age=15):
    if not value or value.get('source') != 'bridge_heating_v1':
        return False
    try:
        now = utc(now)
        return (-2 <= (now-utc(value['observed_at'])).total_seconds() <= max_age
                and 0 <= (now-utc(value['received_at'])).total_seconds() <= max_age)
    except (ValueError, TypeError, KeyError):
        return False
