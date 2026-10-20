"""Heating delivery 1: configuration isolation, no actuation, additive migration."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from tests.test_dashboard_runtime import (app, client, _login_admin, _criar_actor,
    _criar_plant_vessel_mapping, db, BrewPlant, BrewPlantVessel, BrewPlantMapping,
    BrewSession, DashboardLayout, DashboardWidget, device_service)
from addons.addon_brewstation.features.feature_mash_control.services import (
    heating_configuration_service as heating, dashboard_runtime_service as runtime)


def profile(**extra):
    return dict(usage="sparge", target_temp="76,5", planned_volume_liters="25",
                expected_version=0, **extra)


def source(**extra):
    value = dict(name="Fogareiro GLP", type="gas", role="auxiliary", mode="manual",
                 enabled=True, nominal_power_kw="8", expected_version=0)
    value.update(extra)
    return value


def test_profile_sources_and_snapshot_never_command_hardware(app, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Preparation must not send commands")
    monkeypatch.setattr(device_service, "set_value", forbidden)
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping()
        sensor = _criar_actor(name="heat_temp", function_name="mash_temp")
        device_service.update_from_mqtt(sensor, 64.5)
        heating.save_profile(vessel, profile(primary_sensor_mapping_id=mapping.id))
        heating.save_source(vessel, source(expected_version=1))
        data = heating.snapshot(vessel)
        assert data["temperature"] == 64.5
        assert data["target_temp"] == 76.5
        assert data["planned_volume_liters"] == 25
        assert data["usage"] == "sparge"
        assert data["sources"][0]["type"] == "gas"
        assert data["sources"][0]["state"] == "sem confirmação de funcionamento"
        assert data["automatic_demand_percent"] is None
        assert data["can_actuate"] is False
        layout = DashboardLayout(name="HLT", plant_id=plant.id)
        db.session.add(layout); db.session.commit()
        widget = runtime.create_widget_from_editor(layout, widget_type="heating", label_text="HLT", x=0, y=0, vessel_id=vessel.id)
        widget.device_function_name = "forged_actuator"
        assert runtime.set_widget_value(widget, True)["ok"] is False
        assert runtime.get_layout_snapshot(layout)["widgets"][widget.id]["usage"] == "sparge"
        source_id = heating.config(vessel)["sources"][0]["id"]
        heating.remove_source(vessel, source_id, {"expected_version": 2})
        assert heating.config(vessel)["sources"] == []


def test_conflict_and_active_session_preserve_configuration(app):
    with app.app_context():
        plant, vessel, _ = _criar_plant_vessel_mapping()
        heating.save_profile(vessel, profile())
        with pytest.raises(heating.HeatingError) as error:
            heating.save_source(vessel, source())
        assert error.value.code == 409
        db.session.rollback()
        assert vessel.heating_version == 1 and heating.config(vessel)["sources"] == []
        for status in ("active", "paused"):
            session = BrewSession(name=status, plant_id=plant.id, status=status)
            db.session.add(session); db.session.commit()
            with pytest.raises(heating.HeatingError) as error:
                heating.save_source(vessel, source(expected_version=1))
            assert error.value.code == 409
            db.session.rollback()
            session.status = "completed"; db.session.commit()
        assert vessel.heating_version == 1


def test_primary_sensor_selection_and_plant_isolation(app):
    with app.app_context():
        _criar_actor(name="one", function_name="one")
        _criar_actor(name="two", function_name="two")
        plant, vessel, first = _criar_plant_vessel_mapping(role_key="temp_one", function_name="one")
        second = BrewPlantMapping(vessel_id=vessel.id, role_key="temp_two", device_function_name="two")
        db.session.add(second); db.session.commit()
        assert heating.primary_sensor(vessel) is None
        heating.save_profile(vessel, profile(primary_sensor_mapping_id=second.id))
        assert heating.primary_sensor(vessel).id == second.id
        other, foreign, foreign_mapping = _criar_plant_vessel_mapping(plant_name="Foreign", function_name="one")
        invalid = profile(primary_sensor_mapping_id=foreign_mapping.id)
        invalid["expected_version"] = 1
        with pytest.raises(heating.HeatingError):
            heating.save_profile(vessel, invalid)
        layout = DashboardLayout(name="Own", plant_id=plant.id)
        db.session.add(layout); db.session.commit()
        for wrong in (foreign.id, [], {}, True, "invalid"):
            with pytest.raises(runtime.DashboardEditorError):
                runtime.create_widget_from_editor(layout, widget_type="heating", label_text="x", x=0, y=0, vessel_id=wrong)
        heating.save_source(vessel, source(expected_version=1))
        with pytest.raises(heating.HeatingError):
            heating.save_source(vessel, source(role="primary", device_function_name="two", expected_version=2))


@pytest.mark.parametrize("temperature", ["nan", "inf", "-1", "111", True, {}, []])
def test_reject_invalid_planned_temperature(app, temperature):
    with app.app_context():
        _, vessel, _ = _criar_plant_vessel_mapping()
        data = profile(); data["target_temp"] = temperature
        with pytest.raises(heating.HeatingError):
            heating.save_profile(vessel, data)
        assert vessel.heating_version == 0


def test_hlt_default_and_generic_crud_cannot_bypass_configuration(app):
    from addons.addon_brewstation.features.feature_mash_control.services.brew_plant_vessel_service import BrewPlantVesselService
    with app.app_context():
        _, vessel, _ = _criar_plant_vessel_mapping()
        vessel.vessel_type = "hlt"; db.session.commit()
        assert heating.config(vessel)["usage"] == "hlt"
        BrewPlantVesselService()._apply_fields(vessel, {"heating_config_json": {"sources": []}, "heating_version": 20})
        assert vessel.heating_config_json is None and vessel.heating_version == 0


def test_routes_widget_editor_and_workspace(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant, vessel, _ = _criar_plant_vessel_mapping()
        layout = DashboardLayout(name="Heating", plant_id=plant.id)
        db.session.add(layout); db.session.commit()
        plant_id, vessel_id, layout_id = plant.id, vessel.id, layout.id
    base = f"/brewstation/plant-workspace/{plant_id}/vessels/{vessel_id}/heating"
    assert client.post(base + "/profile", json=profile()).status_code == 200
    assert client.post(base + "/source", json=source()).status_code == 409
    assert client.post(base + "/source", json=source(expected_version=1)).status_code == 200
    fragment = client.get(f"/brewstation/plant-workspace/{plant_id}/tab/plant")
    assert fragment.status_code == 200
    assert b"Fogareiro GLP" in fragment.data and b"sparge" in fragment.data
    response = client.post(f"/brewstation/dashboards/{layout_id}/widgets", json={"widget_type": "heating", "label_text": "HLT", "vessel_id": vessel_id, "x": 0, "y": 0})
    assert response.status_code == 200, response.json
    widget_id = response.json["widget_id"]
    view = client.get(f"/brewstation/dashboards/{layout_id}/view")
    assert view.status_code == 200 and b"db-heating-body" in view.data
    assert client.post(f"/brewstation/dashboards/widgets/{widget_id}/config", json={"vessel_id": []}).status_code == 400
    assert client.post(f"/brewstation/dashboards/widgets/{widget_id}/config", json={"vessel_id": None}).status_code == 200
    with app.app_context():
        assert db.session.get(DashboardWidget, widget_id).vessel_id is None
    client.post("/api/auth/logout")
    assert client.post(base + "/profile", json=profile()).status_code in (302, 401)


def migration():
    path = Path(__file__).resolve().parents[1] / "migrations/versions/b04e7c98d216_mash_heating_configuration.py"
    spec = importlib.util.spec_from_file_location("heating_migration", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_migration_preserves_rows_and_blocks_loss():
    module = migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text(f'CREATE TABLE "{module.TABLE}" (id INTEGER PRIMARY KEY, label TEXT)'))
        connection.execute(sa.text(f'INSERT INTO "{module.TABLE}" VALUES (1, \'Legacy HLT\')'))
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade(); module.upgrade()
        assert connection.execute(sa.text(f'SELECT label, heating_version FROM "{module.TABLE}"')).one() == ("Legacy HLT", 0)
        module.downgrade(); module.upgrade()
        connection.execute(sa.text(f'UPDATE "{module.TABLE}" SET heating_config_json = :value'), {"value": '{"usage":"hlt"}'})
        with pytest.raises(RuntimeError, match="Downgrade bloqueado"):
            module.downgrade()
        assert connection.execute(sa.text(f'SELECT label FROM "{module.TABLE}"')).scalar() == "Legacy HLT"


def test_migration_rejects_incompatible_existing_column():
    module = migration()
    with sa.create_engine("sqlite://").begin() as connection:
        connection.execute(sa.text(f'CREATE TABLE "{module.TABLE}" (id INTEGER, heating_config_json TEXT)'))
        module.op = Operations(MigrationContext.configure(connection))
        with pytest.raises(RuntimeError, match="incompatível"):
            module.upgrade()


def test_non_admin_cannot_modify_heating(app, client):
    from model.core.user import User
    with app.app_context():
        plant, vessel, _ = _criar_plant_vessel_mapping()
        user = User(username="heating_reader", email="reader@test.local", nome="Reader",
                    nome_completo="Reader", celular="0", is_admin=False, is_active=True)
        user.set_password("reader123")
        db.session.add(user); db.session.commit()
        path = f"/brewstation/plant-workspace/{plant.id}/vessels/{vessel.id}/heating/profile"
    client.post("/api/auth/login", json={"username": "heating_reader", "password": "reader123"})
    assert client.post(path, json=profile()).status_code == 403


def test_source_actuator_scope_uniqueness_and_legacy_sensor(app):
    with app.app_context():
        _criar_actor(name="temp", function_name="temp")
        _criar_actor(name="heater", function_name="heater", category="actuator", actor_type="actuator")
        plant, vessel, mapping = _criar_plant_vessel_mapping(function_name="temp")
        assert heating.primary_sensor(vessel).id == mapping.id
        with pytest.raises(heating.HeatingError, match="mapeada neste tanque"):
            heating.save_source(vessel, source(device_function_name="heater"))
        db.session.add(BrewPlantMapping(vessel_id=vessel.id, role_key="actor_heat", device_function_name="heater"))
        db.session.commit()
        heating.save_source(vessel, source(type="electric", role="primary", device_function_name="heater"))
        for extra in ({"role": "primary"}, {"device_function_name": "heater"}):
            with pytest.raises(heating.HeatingError):
                heating.save_source(vessel, source(expected_version=1, **extra))
        assert len(heating.config(vessel)["sources"]) == 1


@pytest.mark.parametrize("usage,expected", [("process", 65), ("hlt", 76.5), ("sparge", 76.5)])
def test_hlt_sparge_target_is_independent_of_mash_step(app, usage, expected):
    from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
    with app.app_context():
        plant, vessel, _ = _criar_plant_vessel_mapping()
        data = profile(); data["usage"] = usage
        heating.save_profile(vessel, data)
        session = BrewSession(name="Mash with hot water", plant_id=plant.id, status="active")
        db.session.add(session); db.session.flush()
        db.session.add(BrewSessionStep(session_id=session.id, vessel_id=vessel.id,
            name="Mash", step_index=1, target_temp=65, status="active"))
        db.session.commit()
        assert heating.snapshot(vessel, session)["target_temp"] == expected
