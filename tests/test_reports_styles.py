"""Propriedades visuais: contrato tipado, segurança e compatibilidade."""
import pytest
from addons.addon_reports.root.services.report_layout_service import ReportLayoutService, ReportError
from tests.test_reports_workspace import app, client, create, read, save, post


def text_layout(style=None):
    props = {'text':'Título'}
    if style is not None:
        props['style'] = style
    return {'schema_version':1,'body':[{'id':'title','type':'text','props':props}]}


@pytest.mark.parametrize('style', [
    {'align':'left; background:url(https://evil)'}, {'font_size':True}, {'font_size':7},
    {'font_size':49}, {'bold':'true'}, {'margin_top':-1}, {'padding':25},
    {'background':'red'}, {'font_size':float('nan')}, [], {'cell_padding':5},
])
def test_invalid_styles_rejected(style):
    with pytest.raises(ReportError):
        ReportLayoutService.render(text_layout(style), {}, {})


def test_typed_styles_render_and_legacy_layout_remains_valid():
    assert '<p>Título</p>' in ReportLayoutService.render(text_layout(), {}, {})
    html = ReportLayoutService.render(text_layout({'font_size':24,'bold':True,'align':'right','margin_bottom':12,'padding':0}), {}, {})
    assert 'font-size:24pt' in html and 'font-weight:700' in html
    assert 'text-align:right' in html and 'margin-bottom:12pt' in html and 'padding:0pt' in html


def table_layout():
    return {'schema_version':1,'body':[{'id':'table','type':'table','props':{
        'style':{'cell_padding':8},'collection':{'source':'data','path':['items']},
        'columns':[{'label':'Valor','binding':{'source':'item','path':['value']},'width':40,'align':'right'},
                   {'label':'Nome','binding':{'source':'item','path':['name']},'width':60}],
    }}]}


def test_table_column_styles_apply_to_headers_and_cells():
    html=ReportLayoutService.render(table_layout(),{'items':[{'value':0,'name':'A'}]}, {})
    assert '--report-cell-padding:8pt' in html
    assert '<th style="width:40%;text-align:right">Valor</th>' in html
    assert '<td style="width:40%;text-align:right">0</td>' in html


@pytest.mark.parametrize('change', [{'width':True},{'width':0},{'width':101},{'align':'evil'},{'css':'color:red'}])
def test_invalid_column_style_rejected(change):
    layout=table_layout();layout['body'][0]['props']['columns'][0].update(change)
    with pytest.raises(ReportError):ReportLayoutService.validate(layout)


def test_column_width_total_rejected():
    layout=table_layout();layout['body'][0]['props']['columns'][0]['width']=80
    with pytest.raises(ReportError):ReportLayoutService.validate(layout)


def test_visual_properties_persist_publish_and_clone(client):
    obj=create(client);value=read(client,obj['id'])
    value['layout']=text_layout({'font_size':24,'align':'center','bold':False})
    assert save(client,obj['id'],value).status_code==200
    assert read(client,obj['id'])['layout']==value['layout']
    preview=post(client,f"/templates/{obj['id']}/versions/1/preview",{})
    assert 'font-size:24pt' in preview.json['html']
    assert post(client,f"/templates/{obj['id']}/versions/1/publish",{'lock_version':2}).status_code==200
    assert post(client,f"/templates/{obj['id']}/versions/1/clone",{}).status_code==201
    assert read(client,obj['id'],2)['layout']==value['layout']
