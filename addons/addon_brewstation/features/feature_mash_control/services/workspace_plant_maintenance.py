"""Manutenção reversível sem cascata; não altera controles ou estoque."""
from datetime import datetime, timezone
from sqlalchemy import or_, update
from core.db import db
from services.core.i18n_service import translate as t
from ..model.brew_plant import BrewPlant
from ..model.brew_plant_vessel import BrewPlantVessel
from ..model.brew_plant_mapping import BrewPlantMapping
from ..model.brew_session import BrewSession
from ..model.brew_session_step import BrewSessionStep
from ..model.dashboard_widget import DashboardWidget
from ..model.automation_rule import AutomationRule
from addons.addon_device_manager.root.services.device_function_lookup import get_function_by_name


class MaintenanceNotFound(ValueError): pass
class MaintenanceConflict(ValueError): pass


def _message(key): return t("brewstation_mashctrl.maintenance." + key)


def maintain(plant_id, kind, record_id, action):
    try:
        db.session.execute(update(BrewPlant).where(BrewPlant.id == plant_id).values(
            updated_at=BrewPlant.updated_at).execution_options(synchronize_session=False))
        plant = BrewPlant.query.filter_by(id=plant_id, is_deleted=False).first()
        if plant is None: raise MaintenanceNotFound(_message("not_found"))
        if kind == "vessels":
            row = BrewPlantVessel.query.filter_by(id=record_id, plant_id=plant_id).first()
            vessel = row
        elif kind == "mappings":
            row = BrewPlantMapping.query.join(BrewPlantVessel).filter(
                BrewPlantMapping.id == record_id, BrewPlantVessel.plant_id == plant_id).first()
            vessel = row.vessel if row else None
        else: raise ValueError(_message("invalid_action"))
        if row is None: raise MaintenanceNotFound(_message("not_found"))
        if action not in ("trash", "restore"): raise ValueError(_message("invalid_action"))
        deleted = action == "trash"
        if row.is_deleted == deleted:
            db.session.commit()
            return row.to_dict()
        if BrewSession.query.filter(BrewSession.plant_id == plant_id, BrewSession.is_deleted.is_(False),
                                    BrewSession.status.in_(("draft", "active", "paused"))).first():
            raise MaintenanceConflict(_message("open_sessions"))
        if kind == "vessels" and deleted:
            if BrewPlantMapping.query.filter_by(vessel_id=row.id, is_deleted=False).first():
                raise MaintenanceConflict(_message("mappings"))
            if DashboardWidget.query.filter_by(vessel_id=row.id).first() or BrewSessionStep.query.filter_by(vessel_id=row.id).first():
                raise MaintenanceConflict(_message("references"))
            for connection in (plant.plant_schema_json or {}).get("connections", []):
                if isinstance(connection, dict) and any(str(connection.get(key)) == str(row.id) for key in ("from_vessel_id", "to_vessel_id")):
                    raise MaintenanceConflict(_message("connections"))
        if kind == "mappings":
            if vessel.is_deleted: raise MaintenanceConflict(_message("restore_vessel"))
            name = row.device_function_name
            if any(isinstance(connection, dict) and connection.get("flow_function_name") == name
                   for connection in (plant.plant_schema_json or {}).get("connections", [])):
                raise MaintenanceConflict(_message("connections"))
            if AutomationRule.query.filter(AutomationRule.is_active.is_(True), AutomationRule.is_deleted.is_(False),
                    or_(AutomationRule.sensor_function_name == name, AutomationRule.actor_function_name == name)).first():
                raise MaintenanceConflict(_message("rules"))
            if deleted and DashboardWidget.query.filter(DashboardWidget.is_deleted.is_(False), or_(
                    DashboardWidget.vessel_id == vessel.id, DashboardWidget.device_function_name == name)).first():
                raise MaintenanceConflict(_message("references"))
            if not deleted:
                if BrewPlantMapping.query.filter(BrewPlantMapping.vessel_id == vessel.id,
                        BrewPlantMapping.role_key == row.role_key, BrewPlantMapping.is_deleted.is_(False),
                        BrewPlantMapping.id != row.id).first():
                    raise MaintenanceConflict(_message("duplicate"))
                function = get_function_by_name(name)
                category = {"sensor_temp": "sensor", "actor_heat": "actuator", "actor_flow": "actuator"}.get(row.role_key)
                if not function or (category and function.get("category") not in (category, "hybrid")):
                    raise MaintenanceConflict(_message("function"))
        row.is_deleted = deleted
        row.deleted_at = datetime.now(timezone.utc) if deleted else None
        db.session.commit()
        return row.to_dict()
    except Exception:
        db.session.rollback()
        raise
