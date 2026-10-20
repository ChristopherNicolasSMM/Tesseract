"""Plant-scoped heating preparation. This service NEVER commands hardware.

A vessel owns its sources; weak device references remain function names. Rules and
actual PID telemetry are subsequent deliveries, not inferred from command cache.
"""
from copy import deepcopy
import math
from uuid import uuid4
from sqlalchemy import update
from core.db import db
from ..model.brew_plant import BrewPlant
from ..model.brew_plant_vessel import BrewPlantVessel
from ..model.brew_plant_mapping import BrewPlantMapping
from ..model.brew_session import BrewSession
from addons.addon_device_manager.root.services.device_function_lookup import get_function_by_name

USAGES = {"process": "Processo / etapa da sessão", "hlt": "Água quente (HLT)", "sparge": "Água para lavagem (sparge)"}
SOURCE_TYPES = {"electric": "Elétrico", "gas": "Gás", "other": "Outro"}
SOURCE_ROLES = {"primary": "Principal", "auxiliary": "Auxiliar"}
MODES = {"manual": "Manual", "advisory": "Solicitação ao operador (futura)"}
PROTECTIONS = {"flame": "Supervisão de chama", "gas_leak": "Vazamento de gás", "minimum_level": "Nível mínimo", "flow": "Fluxo", "over_temperature": "Sobretemperatura independente"}


class HeatingError(ValueError):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code


def scoped_vessel(plant_id, vessel_id):
    if isinstance(vessel_id, bool) or not isinstance(vessel_id, (int, str)):
        raise HeatingError("Identificação do tanque inválida.")
    try:
        vessel_id = int(vessel_id)
    except ValueError:
        raise HeatingError("Identificação do tanque inválida.") from None
    vessel = BrewPlantVessel.query.join(BrewPlant).filter(
        BrewPlantVessel.id == vessel_id, BrewPlantVessel.plant_id == plant_id,
        BrewPlantVessel.is_deleted.is_(False), BrewPlant.is_deleted.is_(False)).first()
    if vessel is None:
        raise HeatingError("Tanque desta planta não encontrado.", 404)
    return vessel


def config(vessel):
    value = {"usage": "hlt" if vessel.vessel_type == "hlt" else "process",
             "primary_sensor_mapping_id": None, "target_temp": None,
             "planned_volume_liters": None, "sources": []}
    if isinstance(vessel.heating_config_json, dict):
        value.update(deepcopy(vessel.heating_config_json))
    return value


def mappings(vessel):
    return BrewPlantMapping.query.filter_by(vessel_id=vessel.id, is_deleted=False).order_by(BrewPlantMapping.id).all()


def sensor_options(vessel):
    result = []
    for mapping in mappings(vessel):
        meta = get_function_by_name(mapping.device_function_name)
        if (meta and meta.get("category") in ("sensor", "hybrid")
                and meta.get("data_type") in ("float", "int")
                and ("temp" in mapping.role_key or meta.get("unit") in ("°C", "C", "degC"))):
            result.append(mapping)
    return result


def primary_sensor(vessel):
    options = sensor_options(vessel)
    configured = config(vessel)["primary_sensor_mapping_id"]
    if configured is not None:
        return next((m for m in options if m.id == configured), None)
    # Legacy single/canonical sensor remains usable; multiple noncanonical require choice.
    canonical = [m for m in options if m.role_key == "sensor_temp"]
    return canonical[0] if len(canonical) == 1 else options[0] if len(options) == 1 else None


def _number(raw, label, low, high):
    if raw in (None, ""):
        return None
    if isinstance(raw, bool):
        raise HeatingError(f"{label}: informe número válido.")
    try:
        value = float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        raise HeatingError(f"{label}: informe número válido.") from None
    if not math.isfinite(value) or not low <= value <= high:
        raise HeatingError(f"{label}: use valor entre {low} e {high}.")
    return value


def _enum(raw, choices, label):
    if not isinstance(raw, str) or raw not in choices:
        raise HeatingError(f"{label} inválido.")
    return raw


def _save(vessel, value, expected_version):
    # Serialize against existing workspace maintenance operations too.
    db.session.execute(update(BrewPlant).where(BrewPlant.id == vessel.plant_id).values(updated_at=BrewPlant.updated_at))
    if not BrewPlant.query.filter_by(id=vessel.plant_id, is_deleted=False).first():
        raise HeatingError("Planta não encontrada.", 404)
    if BrewSession.query.filter(BrewSession.plant_id == vessel.plant_id,
            BrewSession.is_deleted.is_(False), BrewSession.status.in_(("active", "paused"))).first():
        raise HeatingError("Encerre as sessões ativas/pausadas antes de alterar o aquecimento.", 409)
    try:
        version = int(expected_version)
        if str(version) != str(expected_version).strip() or version < 0:
            raise ValueError
    except (ValueError, TypeError):
        raise HeatingError("Versão inválida; recarregue a configuração.", 409) from None
    result = db.session.execute(update(BrewPlantVessel).where(
        BrewPlantVessel.id == vessel.id, BrewPlantVessel.plant_id == vessel.plant_id,
        BrewPlantVessel.is_deleted.is_(False), BrewPlantVessel.heating_version == version).values(
            heating_config_json=value, heating_version=version + 1).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        raise HeatingError("A configuração mudou. Recarregue antes de salvar.", 409)
    db.session.commit()
    db.session.refresh(vessel)
    return config(vessel)


def save_profile(vessel, data):
    value = config(vessel)
    value["usage"] = _enum(data.get("usage"), USAGES, "Uso")
    selected = data.get("primary_sensor_mapping_id")
    if isinstance(selected, bool) or (selected is not None and not isinstance(selected, (str, int))):
        raise HeatingError("Sensor inválido.")
    try:
        selected = int(selected) if selected not in (None, "") else None
    except (ValueError, TypeError):
        raise HeatingError("Sensor inválido.") from None
    if selected is not None and selected not in {m.id for m in sensor_options(vessel)}:
        raise HeatingError("Selecione um sensor de temperatura deste tanque.")
    value["primary_sensor_mapping_id"] = selected
    value["target_temp"] = _number(data.get("target_temp"), "Temperatura planejada (°C)", 0, 110)
    value["planned_volume_liters"] = _number(data.get("planned_volume_liters"), "Volume planejado (L)", 0, 100000)
    return _save(vessel, value, data.get("expected_version"))


def save_source(vessel, data, source_id=None):
    value = config(vessel)
    existing = next((s for s in value["sources"] if s["id"] == source_id), None)
    if source_id and existing is None:
        raise HeatingError("Fonte deste tanque não encontrada.", 404)
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 100:
        raise HeatingError("Informe nome da fonte com até 100 caracteres.")
    role = _enum(data.get("role"), SOURCE_ROLES, "Participação")
    if role == "primary" and any(s["role"] == "primary" and s["id"] != source_id for s in value["sources"]):
        raise HeatingError("Já existe fonte principal. Altere a participação dela antes de cadastrar outra.")
    function_name = str(data.get("device_function_name") or "").strip() or None
    if function_name:
        linked = [m for m in mappings(vessel) if m.device_function_name == function_name]
        meta = get_function_by_name(function_name)
        if not linked or not meta or meta.get("category") not in ("actuator", "hybrid"):
            raise HeatingError("Associe uma função de atuador já mapeada neste tanque.")
        if any(s.get("device_function_name") == function_name and s["id"] != source_id for s in value["sources"]):
            raise HeatingError("Esta função já está associada a outra fonte do tanque.")
    source = {"id": source_id or str(uuid4()), "name": name,
              "type": _enum(data.get("type"), SOURCE_TYPES, "Tipo"), "role": role,
              "mode": _enum(data.get("mode"), MODES, "Operação"),
              "enabled": data.get("enabled") in (True, "on", "true"),
              "nominal_power_kw": _number(data.get("nominal_power_kw"), "Potência nominal (kW)", 0, 10000),
              "device_function_name": function_name}
    if existing:
        value["sources"] = [source if s["id"] == source_id else s for s in value["sources"]]
    else:
        if len(value["sources"]) >= 20:
            raise HeatingError("Limite de 20 fontes por tanque.")
        value["sources"].append(source)
    return _save(vessel, value, data.get("expected_version"))


def remove_source(vessel, source_id, data):
    value = config(vessel)
    if not any(s["id"] == source_id for s in value["sources"]):
        raise HeatingError("Fonte deste tanque não encontrada.", 404)
    value["sources"] = [s for s in value["sources"] if s["id"] != source_id]
    return _save(vessel, value, data.get("expected_version"))


def snapshot(vessel, session=None):
    from addons.addon_device_manager.root.services import device_service
    from ..model.brew_session_step import BrewSessionStep
    value = config(vessel)
    sensor = primary_sensor(vessel)
    temperature = None
    sensor_status = "não configurado ou seleção inválida"
    if sensor:
        actor_id = device_service.find_unique_actor_external_id_by_function_name(sensor.device_function_name)
        if actor_id:
            observed = device_service.get_value(actor_id)
            if isinstance(observed, (int, float)) and not isinstance(observed, bool) and math.isfinite(observed):
                temperature = observed
            sensor_status = "último valor registrado" if temperature is not None else "sem leitura numérica válida"
        else:
            sensor_status = "dispositivo ausente ou ambíguo"
    target = value["target_temp"]
    target_origin = "planejado no tanque" if target is not None else "não informado"
    if value["usage"] == "process" and session and session.plant_id == vessel.plant_id:
        step = BrewSessionStep.query.filter_by(session_id=session.id, vessel_id=vessel.id, status="active", is_deleted=False).first()
        if step is not None and step.target_temp is not None:
            target = step.target_temp
            target_origin = "etapa da sessão"
    return {"vessel_id": vessel.id, "vessel_name": vessel.label_text, "usage": value["usage"],
            "usage_label": USAGES[value["usage"]], "temperature": temperature,
            "sensor_label": (sensor.label_text or sensor.role_key) if sensor else None,
            "primary_temperature_role_key": sensor.role_key if sensor else None,
            "sensor_status": sensor_status, "target_temp": target, "target_origin": target_origin,
            "planned_volume_liters": value["planned_volume_liters"],
            "sources": [{**s, "type_label": SOURCE_TYPES[s["type"]], "role_label": SOURCE_ROLES[s["role"]],
                         "mode_label": MODES[s["mode"]], "state": "sem confirmação de funcionamento"} for s in value["sources"]],
            "automatic_demand_percent": None, "power_status": "telemetria de demanda não disponível",
            "rule_status": "regras de solicitação previstas para a entrega 2",
            "protections": [{"key": key, "label": label, "state": "não configurada / sem confirmação"} for key, label in PROTECTIONS.items()],
            "can_actuate": False}


def workspace_context(vessels):
    return {"heating_configs": {v.id: config(v) for v in vessels},
            "heating_sensors": {v.id: sensor_options(v) for v in vessels},
            "heating_mappings": {v.id: [m for m in mappings(v) if (get_function_by_name(m.device_function_name) or {}).get("category") in ("actuator", "hybrid")] for v in vessels},
            "heating_function_ids": {v.id: [meta["id"] for m in mappings(v)
                if (meta := get_function_by_name(m.device_function_name)) and meta.get("category") in ("actuator", "hybrid")] for v in vessels},
            "heating_usages": USAGES, "heating_types": SOURCE_TYPES,
            "heating_roles": SOURCE_ROLES, "heating_modes": MODES}
