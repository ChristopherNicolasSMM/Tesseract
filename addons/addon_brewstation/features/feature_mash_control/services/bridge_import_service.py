"""
addons/addon_brewstation/features/feature_mash_control/services/bridge_import_service.py

"Cadastro primário" — importa devices.yml + recipe.yml no formato do
tesseract-device-bridge (github.com/ChristopherNicolasSMM/Tesseract-Device-Bridge,
schema confirmado no README real do projeto) e monta o cadastro
inicial: DeviceFunction/DeviceMetadata/DeviceActor (addon_device_manager)
+ BrewPlant/BrewPlantVessel/BrewPlantMapping + DashboardLayout/
DashboardWidget (mash_control) — sem precisar cadastrar tudo na mão
pelas telas de CRUD.

Idempotente por nome/id do YAML: rodar de novo com o mesmo arquivo (ou
um YAML atualizado com mais devices) reaproveita o que já existe em
vez de duplicar — decisão registrada em conversa/BACKLOG.md.

NÃO gerado pelo CrudGen, não sobrescrito por ele — mesmo padrão de
automation_engine.py/dashboard_runtime_service.py.
"""
from __future__ import annotations

from typing import Any, Optional

import yaml

from core.db import db
from addons.addon_device_manager.root.model.device_metadata import DeviceMetadata
from addons.addon_device_manager.root.model.device_function import DeviceFunction
from addons.addon_device_manager.root.model.device_actor import DeviceActor
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_widget import DashboardWidget


class BridgeImportError(Exception):
    pass


# Sigla de vessel_type conhecida a partir do `id` convencional do
# tesseract-device-bridge (README: "vessels é uma lista... id é a
# referência estável"). Fora dessa lista, cai em "generic" — nunca
# bloqueia a importação por um id não previsto.
_VESSEL_TYPE_BY_ID = {
    "mash": "mash_tun",
    "boil": "boil_kettle",
    "hlt": "hlt",
    "whirlpool": "whirlpool",
    "ferment": "fermenter",
    "fermenter": "fermenter",
}


# ── Parsing ───────────────────────────────────────────────────────────────

def parse_devices_yaml(text: str) -> list[dict]:
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise BridgeImportError(f"devices.yml inválido: {exc}") from exc
    devices = data.get("devices")
    if not isinstance(devices, list):
        raise BridgeImportError("devices.yml precisa ter uma chave 'devices' (lista).")
    return devices


def parse_recipe_yaml(text: str) -> dict:
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise BridgeImportError(f"recipe.yml inválido: {exc}") from exc
    if "vessels" not in data:
        raise BridgeImportError("recipe.yml precisa ter uma chave 'vessels' (lista).")
    return data


# ── DeviceFunction / DeviceActor (skill 02 — mesmo Addon, FK real) ──────────

def _function_category(role: str) -> str:
    return "actuator" if role == "actuator" else "sensor"


def _function_data_type(role: str) -> str:
    return "bool" if role == "actuator" else "float"


def _function_icon(role: str, subtype: Optional[str]) -> str:
    if role == "actuator":
        return "bi-lightning-charge-fill"
    if subtype == "temperature":
        return "bi-thermometer-half"
    return "bi-cpu"


def _get_or_create_bridge_device(bridge_device_name: str) -> tuple[DeviceMetadata, bool]:
    existing = DeviceMetadata.query.filter_by(name=bridge_device_name, is_deleted=False).first()
    if existing:
        return existing, False
    device = DeviceMetadata(
        name=bridge_device_name, device_type="gateway", protocol="mqtt", is_active=True,
    )
    db.session.add(device)
    db.session.flush()
    return device, True


def _import_devices(devices: list[dict], bridge_device: DeviceMetadata) -> dict:
    functions_created, functions_reused = [], []
    actors_created, actors_reused = [], []

    for entry in devices:
        function_name = entry.get("id")
        if not function_name:
            continue

        function = DeviceFunction.query.filter_by(name=function_name).first()
        if function:
            functions_reused.append(function_name)
        else:
            role = entry.get("role", "sensor")
            simulated = entry.get("simulated") or {}
            function = DeviceFunction(
                name=function_name,
                display_name=entry.get("name") or function_name,
                category=_function_category(role),
                unit=entry.get("unit"),
                data_type=_function_data_type(role),
                min_value=simulated.get("min"),
                max_value=simulated.get("max"),
                icon=_function_icon(role, entry.get("subtype")),
                is_predefined=False,
            )
            db.session.add(function)
            db.session.flush()
            functions_created.append(function_name)

        existing_actor = DeviceActor.query.filter_by(function_id=function.id, is_deleted=False).first()
        if existing_actor:
            actors_reused.append(function_name)
            continue

        hardware = entry.get("hardware") or {}
        port_name = hardware.get("address") or (f"GPIO{hardware['pin']}" if "pin" in hardware else "N/A")
        failsafe_value = entry.get("failsafe_value")
        actor = DeviceActor(
            device_id=bridge_device.id,
            port_name=port_name,
            function_id=function.id,
            actor_type=entry.get("role", "sensor"),
            name=entry.get("name") or function_name,
            failsafe_value=str(failsafe_value) if failsafe_value is not None else None,
            is_risk=bool(entry.get("is_risk", False)),
            is_active=True,
        )
        db.session.add(actor)
        db.session.flush()
        actors_created.append(function_name)

    return {
        "functions_created": functions_created, "functions_reused": functions_reused,
        "actors_created": actors_created, "actors_reused": actors_reused,
    }


# ── BrewPlant / Vessel / Mapping / Dashboard ─────────────────────────────────

def _get_or_create_plant(plant_name: str) -> tuple[BrewPlant, bool]:
    existing = BrewPlant.query.filter_by(name=plant_name, is_deleted=False).first()
    if existing:
        return existing, False
    plant = BrewPlant(name=plant_name)
    db.session.add(plant)
    db.session.flush()
    return plant, True


def _distinct_pumps_for_vessel(steps: list[dict], vessel_id: str) -> list[str]:
    seen: list[str] = []
    for step in steps:
        if step.get("vessel") != vessel_id:
            continue
        for pump in step.get("pumps") or []:
            if pump not in seen:
                seen.append(pump)
    return seen


def _import_recipe(recipe: dict, plant: BrewPlant) -> dict:
    vessels_created, vessels_reused = [], []
    mappings_created, mappings_reused = [], []
    vessel_obj_by_yaml_id: dict[str, BrewPlantVessel] = {}

    yaml_vessels = sorted(recipe.get("vessels") or [], key=lambda v: v.get("order", 0))
    steps = recipe.get("steps") or []

    for v in yaml_vessels:
        label_text = v.get("name") or v.get("id")
        vessel = BrewPlantVessel.query.filter_by(
            plant_id=plant.id, label_text=label_text, is_deleted=False,
        ).first()
        if vessel:
            vessels_reused.append(label_text)
        else:
            vessel = BrewPlantVessel(
                plant_id=plant.id,
                vessel_type=_VESSEL_TYPE_BY_ID.get(v.get("id"), "generic"),
                label_text=label_text,
                position_order=v.get("order", 0),
            )
            db.session.add(vessel)
            db.session.flush()
            vessels_created.append(label_text)
        vessel_obj_by_yaml_id[v.get("id")] = vessel

        role_targets = [("sensor_temp", v.get("sensor_device_id")), ("actor_heat", v.get("heater_device_id"))]
        for i, pump in enumerate(_distinct_pumps_for_vessel(steps, v.get("id")), start=1):
            role_targets.append((f"actor_pump_{i}", pump))

        for role_key, function_name in role_targets:
            if not function_name:
                continue
            existing_mapping = BrewPlantMapping.query.filter_by(
                vessel_id=vessel.id, role_key=role_key, is_deleted=False,
            ).first()
            if existing_mapping:
                mappings_reused.append(f"{label_text}.{role_key}")
                continue
            db.session.add(BrewPlantMapping(
                vessel_id=vessel.id, role_key=role_key, device_function_name=function_name,
                label_text=role_key.replace("_", " ").title(),
            ))
            mappings_created.append(f"{label_text}.{role_key}")

    # Tubulação (conversa — arquitetura de dashboard): conecta vasilhames
    # consecutivos (por `order`) quando o vasilhame de destino usa bomba
    # em algum step — melhor esforço, editável depois via
    # plant.plant_schema_json (skill: sem tela própria pra isso ainda).
    connections = []
    for prev_v, next_v in zip(yaml_vessels, yaml_vessels[1:]):
        pumps = _distinct_pumps_for_vessel(steps, next_v.get("id"))
        if not pumps:
            continue
        from_vessel = vessel_obj_by_yaml_id.get(prev_v.get("id"))
        to_vessel = vessel_obj_by_yaml_id.get(next_v.get("id"))
        if from_vessel and to_vessel:
            connections.append({
                "from_vessel_id": from_vessel.id, "to_vessel_id": to_vessel.id,
                "flow_function_name": pumps[0],
            })
    if connections:
        plant.plant_schema_json = {"connections": connections}

    return {
        "vessels_created": vessels_created, "vessels_reused": vessels_reused,
        "mappings_created": mappings_created, "mappings_reused": mappings_reused,
        "vessel_objs": list(vessel_obj_by_yaml_id.values()),
    }


def _get_or_create_layout(layout_name: str, plant: BrewPlant) -> tuple[DashboardLayout, bool]:
    existing = DashboardLayout.query.filter_by(name=layout_name, is_deleted=False).first()
    if existing:
        return existing, False
    is_default = DashboardLayout.query.filter_by(is_default=True, is_deleted=False).first() is None
    layout = DashboardLayout(name=layout_name, plant_id=plant.id, is_default=is_default)
    db.session.add(layout)
    db.session.flush()
    return layout, True


def _import_dashboard(layout_name: str, plant: BrewPlant, vessels: list[BrewPlantVessel]) -> dict:
    layout, layout_created = _get_or_create_layout(layout_name, plant)
    widgets_created, widgets_reused = [], []

    x = 40
    for i, vessel in enumerate(vessels):
        existing_widget = DashboardWidget.query.filter_by(
            layout_id=layout.id, vessel_id=vessel.id, is_deleted=False,
        ).first()
        if existing_widget:
            widgets_reused.append(vessel.label_text)
            x += 260
            continue
        db.session.add(DashboardWidget(
            layout_id=layout.id, widget_type="vessel", vessel_id=vessel.id,
            label_text=vessel.label_text, x=x, y=80, width=220, height=300, z_index=i + 1,
        ))
        widgets_created.append(vessel.label_text)
        x += 260

    if not DashboardWidget.query.filter_by(layout_id=layout.id, widget_type="alarm_list", is_deleted=False).first():
        db.session.add(DashboardWidget(
            layout_id=layout.id, widget_type="alarm_list", label_text="Alarmes",
            x=x, y=80, width=260, height=300, z_index=len(vessels) + 1,
        ))
        widgets_created.append("Alarmes (lista)")
    else:
        widgets_reused.append("Alarmes (lista)")

    return {
        "layout_id": layout.id, "layout_created": layout_created,
        "widgets_created": widgets_created, "widgets_reused": widgets_reused,
    }


# ── Orquestração ──────────────────────────────────────────────────────────

def import_bridge_config(
    devices_yaml_text: str,
    recipe_yaml_text: Optional[str] = None,
    *,
    bridge_device_name: str = "Bridge Principal",
    plant_name: Optional[str] = None,
    layout_name: str = "Painel de Mostura",
) -> dict:
    """
    Ponto de entrada único — "cadastro primário" a partir dos arquivos
    reais do tesseract-device-bridge. `recipe_yaml_text` é opcional
    (README do bridge: "o bridge ainda funciona como painel manual +
    ponte MQTT pura" sem receita) — sem ele, só devices são
    importados, sem planta/vasilhame/dashboard.
    """
    devices = parse_devices_yaml(devices_yaml_text)
    bridge_device, bridge_created = _get_or_create_bridge_device(bridge_device_name)
    device_result = _import_devices(devices, bridge_device)

    result: dict[str, Any] = {
        "bridge_device_id": bridge_device.id, "bridge_device_created": bridge_created,
        **device_result,
        "plant_id": None, "layout_id": None,
    }

    if recipe_yaml_text:
        recipe = parse_recipe_yaml(recipe_yaml_text)
        final_plant_name = plant_name or recipe.get("name") or "Planta Importada"
        plant, plant_created = _get_or_create_plant(final_plant_name)
        recipe_result = _import_recipe(recipe, plant)
        dashboard_result = _import_dashboard(layout_name, plant, recipe_result["vessel_objs"])

        result.update({
            "plant_id": plant.id, "plant_created": plant_created,
            "vessels_created": recipe_result["vessels_created"],
            "vessels_reused": recipe_result["vessels_reused"],
            "mappings_created": recipe_result["mappings_created"],
            "mappings_reused": recipe_result["mappings_reused"],
            "layout_id": dashboard_result["layout_id"],
            "layout_created": dashboard_result["layout_created"],
            "widgets_created": dashboard_result["widgets_created"],
            "widgets_reused": dashboard_result["widgets_reused"],
        })

    db.session.commit()
    return result
