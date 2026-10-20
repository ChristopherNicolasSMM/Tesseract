"""Plant-local controller selection and read-only Bridge heating observations."""
from datetime import datetime, timezone
from addons.addon_device_manager.root.services import device_service
from addons.addon_device_manager.root.services.bridge_heating_telemetry import fresh
from addons.addon_device_manager.root.services.device_function_lookup import get_function_by_name
from . import heating_configuration_service as configuration

OWNER_LABELS = {'local_recipe':'Receita local do Bridge', 'local_manual':'Manual no Bridge',
                'remote_manual':'Override manual remoto', 'failsafe':'Emergência / failsafe', 'idle':'Repouso'}


def controller_options(vessel):
    return [m for m in configuration.mappings(vessel)
            if (get_function_by_name(m.device_function_name) or {}).get('category') in ('actuator','hybrid')]


def read(vessel, now=None, max_age=15):
    now = now or datetime.now(timezone.utc)
    selected = configuration.config(vessel).get('controller_mapping_id')
    mapping = next((m for m in controller_options(vessel) if m.id == selected), None)
    identifier = device_service.find_unique_actor_external_id_by_function_name(mapping.device_function_name) if mapping else None
    telemetry = device_service.get_heating_telemetry(identifier) if identifier else None
    if not telemetry:
        return {'available':False, 'fresh':False, 'status':'Controlador não selecionado ou sem telemetria Bridge v1'}
    is_fresh = fresh(telemetry, now, max_age)
    return {**telemetry, 'available':True, 'fresh':is_fresh,
            'owner_label':OWNER_LABELS.get(telemetry['owner'],telemetry['owner']),
            'status': 'Telemetria recebida' if is_fresh else 'Telemetria antiga; aguarde nova leitura',
            'physical_power_confirmed':False}
