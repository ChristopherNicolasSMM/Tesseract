"""Plant-scoped electrical/pump commands; the Bridge keeps PID ownership."""
from addons.addon_device_manager.root.services import device_service
from addons.addon_device_manager.root.services.bridge_device_control import fresh
from . import heating_configuration_service as configuration


def eligible(vessel):
    controller = configuration.config(vessel).get('controller_mapping_id')
    return [m for m in configuration.mappings(vessel) if m.id == controller or m.role_key.startswith('actor_pump_')]


def identifier(mapping):
    return device_service.find_unique_actor_external_id_by_function_name(mapping.device_function_name)


def view(vessel):
    result = []
    for mapping in eligible(vessel):
        actor = identifier(mapping)
        telemetry = device_service.get_control_telemetry(actor) if actor else None
        if not telemetry:
            continue
        if (mapping.id == configuration.config(vessel).get('controller_mapping_id')) != (telemetry['kind'] == 'power'):
            continue
        result.append({**telemetry, 'mapping_id':mapping.id, 'label':mapping.label_text or mapping.device_function_name,
            'fresh':fresh(telemetry), 'control_url':f'/brewstation/plant-workspace/{vessel.plant_id}/vessels/{vessel.id}/heating/mappings/{mapping.id}/control'})
    return result


def control(vessel, mapping_id, action, value=None):
    mapping = next((m for m in eligible(vessel) if m.id == mapping_id), None)
    if mapping is None:
        raise configuration.HeatingError('Equipamento não pertence ao controle deste tanque.', 404)
    if not any(item['mapping_id'] == mapping_id for item in view(vessel)):
        raise configuration.HeatingError('Controle Bridge não habilitado ou equipamento incompatível.', 409)
    try:
        return device_service.send_device_control(identifier(mapping), action, value)
    except ValueError as exc:
        raise configuration.HeatingError(str(exc), 409) from exc
