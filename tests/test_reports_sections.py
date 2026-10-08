"""Seções preservam composição, formatos e conteúdo entre revisões."""
from tests.test_reports_workspace import app, client, create, read, save, post


def test_nested_section_roundtrip_publish_clone(client):
    obj = create(client)
    value = read(client, obj['id'])
    value['layout'] = {'schema_version': 1, 'body': [
        {'id': 'section', 'type': 'section', 'props': {'style': {'padding': 2}}, 'children': [
            {'id': 'nested', 'type': 'section', 'props': {}, 'children': [
                {'id': 'amount', 'type': 'text', 'props': {
                    'text': '12.50', 'format': {'kind': 'currency', 'currency': 'BRL'},
                    'style': {'bold': True}}}]}]}]}
    assert save(client, obj['id'], value).status_code == 200
    assert read(client, obj['id'])['layout'] == value['layout']
    preview = post(client, f"/templates/{obj['id']}/versions/1/preview", {})
    assert preview.status_code == 200
    assert preview.json['html'].count('<section') == 2
    assert '12,50' in preview.json['html']
    assert 'padding:2pt' in preview.json['html']
    assert post(client, f"/templates/{obj['id']}/versions/1/publish", {'lock_version': 2}).status_code == 200
    assert post(client, f"/templates/{obj['id']}/versions/1/clone", {}).status_code == 201
    assert read(client, obj['id'], 2)['layout'] == value['layout']
