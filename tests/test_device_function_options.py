"""Annotated fixed options, legacy display and server-side validation."""
import pytest
from tests.test_phase6a_device_manager import app, client, _login_admin
from core.db import db
from addons.addon_device_manager.root.model.device_function import DeviceFunction
from addons.addon_device_manager.root.services.device_function_service import DeviceFunctionService
from annotations import get_enum_fields


def test_forms_render_annotated_selects_with_canonical_values(app,client):
    _login_admin(app,client)
    fields={f['field']:f['options'] for f in get_enum_fields(DeviceFunction)}
    assert fields['category']==[{'value':'sensor','label':'Sensor'},{'value':'actuator','label':'Atuador'},{'value':'hybrid','label':'Híbrido'}]
    page=client.get('/device-manager/device-functions/').get_data(as_text=True)
    for field in ('category','data_type'):
        assert f'<select name="{field}"' in page
        assert f'<input type="text" name="{field}"' not in page
    assert '<option value="actuator"' in page and '>Atuador</option>' in page
    assert 'value="actuador"' not in page and 'Selecione uma opção' in page


def test_service_normalizes_alias_and_rejects_invalid_options_with_rollback(app):
    with app.app_context():
        service=DeviceFunctionService()
        result=service.create({'name':'gas','display_name':'Gás','category':'actuador','data_type':'bool'})
        assert result.success and result.data.category=='actuator'
        identifier=result.data.id
        for values in ({'category':'actuatr'},{'data_type':'boolean'}):
            result=service.update(identifier,values)
            assert not result.success and result.code==422
            assert db.session.get(DeviceFunction,identifier).category=='actuator'
            assert db.session.get(DeviceFunction,identifier).data_type=='bool'
        assert not service.create({'name':'bad','display_name':'Inválida','category':'whatever'}).success
        assert DeviceFunction.query.filter_by(name='bad').first() is None


def test_api_cannot_bypass_select_values(app,client):
    _login_admin(app,client)
    base='/api/device-manager/device-functions/'
    response=client.post(base,json={'name':'gas','display_name':'Gás','category':'actuator','data_type':'bool'})
    assert response.status_code==201,response.data
    identifier=response.get_json()['item']['id']
    invalid=client.put(base+str(identifier),json={'category':'actuatr'})
    assert invalid.status_code==422,invalid.data
    assert client.get(base+str(identifier)).get_json()['item']['category']=='actuator'


def test_edit_preserves_alias_selection_and_marks_unknown_legacy_values(app,client):
    from sqlalchemy import update
    _login_admin(app,client)
    with app.app_context():
        obj=DeviceFunction(name='legacy',display_name='Antiga',category='actuator')
        db.session.add(obj);db.session.commit();identifier=obj.id
        db.session.execute(update(DeviceFunction).where(DeviceFunction.id==identifier).values(category='actuador'));db.session.commit()
    url=f'/device-manager/device-functions/{identifier}'
    page=client.get(url).get_data(as_text=True)
    assert '<option value="actuator" selected>Atuador</option>' in page
    with app.app_context():
        # Reading the selector does not migrate or rewrite the existing row.
        assert db.session.get(DeviceFunction,identifier).category=='actuador'
        db.session.execute(update(DeviceFunction).where(DeviceFunction.id==identifier).values(category='unknown_legacy'));db.session.commit()
    page=client.get(url).get_data(as_text=True)
    assert 'Valor antigo: unknown_legacy' in page and 'disabled selected' in page
    response=client.post(url,data={'name':'legacy','display_name':'Antiga','category':'actuator','data_type':'bool'})
    assert response.status_code==302
    with app.app_context():
        assert db.session.get(DeviceFunction,identifier).category=='actuator'
