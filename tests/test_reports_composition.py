"""Contrato de composição: limites tipados, persistência e HTML de impressão."""
import pytest
from addons.addon_reports.root.services.report_layout_service import ReportLayoutService, ReportError
from tests.test_reports_workspace import app, client, create, read, save, post


def document(columns=2, gap=8):
    return {'schema_version': 1, 'body': [{'id': 'row', 'type': 'section',
        'props': {'columns': columns, 'gap': gap}, 'children': [
            {'id': 'left', 'type': 'section', 'props': {}, 'children': [
                {'id': 'title', 'type': 'text', 'props': {'text': '<Resumo>'}}]},
            {'id': 'right', 'type': 'text', 'props': {'binding': {'source': 'data', 'path': ['amount']},
                'format': {'kind': 'currency'}, 'style': {'bold': True}}}]}]}


@pytest.mark.parametrize('columns,gap', [(0,8),(5,8),(True,8),('2',8),(2,-1),(2,25),(2,True),(2,'8'),(2,1.5)])
def test_reject_invalid_composition(columns, gap):
    with pytest.raises(ReportError):
        ReportLayoutService.validate(document(columns, gap))


def test_composition_escapes_and_formats_children():
    html = ReportLayoutService.render(document(3, 0), {'amount': 12.5}, {})
    assert 'grid-template-columns:repeat(3,minmax(0,1fr));gap:0pt' in html
    assert '&lt;Resumo&gt;' in html and '12,50' in html and 'font-weight:700' in html
    assert '.report-columns { display:block !important; }' in html
    assert '@media print' in html


def test_vertical_section_stays_vertical():
    value = document(1)
    html = ReportLayoutService.render(value, {'amount': 0}, {})
    assert '<section class="report-columns"' not in html
    del value['body'][0]['props']['columns']
    ReportLayoutService.validate(value)


def test_composition_persists_publish_clone(client):
    obj = create(client)
    value = read(client, obj['id'])
    value.update(layout=document(4, 12), data_schema={'type':'object','properties':{'amount':{'type':'number'}},'required':['amount']}, sample_data={'amount':12.5})
    assert save(client, obj['id'], value).status_code == 200
    preview = post(client, f"/templates/{obj['id']}/versions/1/preview", {})
    assert preview.status_code == 200 and 'repeat(4,minmax(0,1fr))' in preview.json['html']
    assert post(client, f"/templates/{obj['id']}/versions/1/publish", {'lock_version':2}).status_code == 200
    assert post(client, f"/templates/{obj['id']}/versions/1/clone", {}).status_code == 201
    assert read(client, obj['id'], 2)['layout'] == value['layout']
