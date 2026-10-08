"""Formatação determinística e parâmetros do catálogo de emissão."""
import pytest
from addons.addon_reports.root.services.report_format_service import validate_format, format_value
from addons.addon_reports.root.services.report_layout_service import ReportLayoutService, ReportError
from tests.test_reports_workspace import app, client, create, read, save, post


@pytest.mark.parametrize('value,spec,expected', [
    ('1234.565',{'kind':'currency'},'R$ 1.234,57'),
    (0,{'kind':'number','decimals':0},'0'),
    (-1234.5,{'kind':'number','decimals':1},'-1.234,5'),
    ('0.25',{'kind':'percent'},'25,00 %'),
    ('12',{'kind':'currency','currency':'USD'},'US$ 12,00'),
    ('2026-10-08',{'kind':'date'},'08/10/2026'),
    ('2026-10-08T12:30:00-03:00',{'kind':'datetime'},'08/10/2026 12:30:00 -0300'),
    (None,{'kind':'currency','null_text':'—'},'—'),
    (False,{'kind':'raw','null_text':'—'},'False'),
])
def test_values(value,spec,expected):
    assert validate_format(spec)
    assert format_value(value,spec)==expected


@pytest.mark.parametrize('spec',[{'kind':'eval'},{'kind':'number','decimals':True},{'kind':'number','decimals':7},{'kind':'date','decimals':2},{'kind':'currency','currency':'X'},{'null_text':5},{'css':'color:red'}])
def test_invalid_format_definition(spec):
    assert not validate_format(spec)
    layout={'schema_version':1,'body':[{'id':'t','type':'text','props':{'text':'A','format':spec}}]}
    with pytest.raises(ReportError):ReportLayoutService.validate(layout)


@pytest.mark.parametrize('value,kind',[('NaN','number'),(True,'number'),('1e100','currency'),('1.234,56','number'),('2026-02-30','date'),('08/10/2026','date'),('bad','datetime')])
def test_invalid_values(value,kind):
    with pytest.raises(ValueError):format_value(value,{'kind':kind})


def test_formatted_content_is_escaped_and_table_preserves_zero():
    layout={'schema_version':1,'body':[{'id':'t','type':'table','props':{
      'collection':{'source':'data','path':['items']},'columns':[
      {'label':'Valor','binding':{'source':'item','path':['value']},'format':{'kind':'currency','null_text':'<script>'}}]}}]}
    html=ReportLayoutService.render(layout,{'items':[{'value':None},{'value':0}]},{})
    assert '&lt;script&gt;' in html and '<script>' not in html and 'R$ 0,00' in html
    with pytest.raises(ReportError) as error:ReportLayoutService.render(layout,{'items':[{'value':'bad'}]}, {})
    assert error.value.code=='reports.error.format'


def test_consumer_catalog_exposes_only_published_parameter_definitions(client):
    obj=create(client);value=read(client,obj['id'])
    value['data_schema']={'type':'object','properties':{'contract':{'const':'estoque.saldos.v1'}}}
    value['parameters']=[{'key':'title','label':'Título','schema':{'type':'string'},'default':'A','required':True}]
    assert save(client,obj['id'],value).status_code==200
    url='/api/reports/consumers/stock/templates'
    assert not any(item['key']==obj['key'] for item in client.get(url).json['items'])
    assert post(client,f"/templates/{obj['id']}/versions/1/publish",{'lock_version':2}).status_code==200
    item=next(item for item in client.get(url).json['items'] if item['key']==obj['key'])
    assert item['parameters']==value['parameters']


def test_format_persists_and_clones(client):
    obj=create(client);value=read(client,obj['id'])
    value['layout']['body'][0]['props']={'text':'1234.5','format':{'kind':'currency','currency':'EUR','decimals':1}}
    assert save(client,obj['id'],value).status_code==200
    assert read(client,obj['id'])['layout']==value['layout']
    html=post(client,f"/templates/{obj['id']}/versions/1/preview",{}).json['html']
    assert '€ 1.234,5' in html
    assert post(client,f"/templates/{obj['id']}/versions/1/clone",{}).status_code==201
    assert read(client,obj['id'],2)['layout']==value['layout']


def test_parameters_distinguish_omitted_null_zero_and_false():
    from addons.addon_reports.root.services.report_template_service import validate_parameters
    definitions=[
      {'key':'count','label':'Contagem','schema':{'type':['integer','null']},'default':3},
      {'key':'flag','label':'Confirmado','schema':{'type':'boolean'},'default':True},
    ]
    assert validate_parameters(definitions,{})=={'count':3,'flag':True}
    assert validate_parameters(definitions,{'count':0,'flag':False})=={'count':0,'flag':False}
    assert validate_parameters(definitions,{'count':None})=={'count':None,'flag':True}
