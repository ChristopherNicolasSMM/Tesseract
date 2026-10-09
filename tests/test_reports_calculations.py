"""Condições sem coerção e totais determinísticos no compositor real."""
import uuid
import pytest
from addons.addon_reports.root.services.report_layout_service import ReportLayoutService, ReportError
from addons.addon_reports.root.services.report_calculation_service import aggregate
from tests.test_reports_workspace import app, client, create, read, save, post


def conditional(expected=True, operator='eq'):
    return {'schema_version':1,'body':[{'id':'group','type':'section','props':{'condition':{
        'binding':{'source':'parameters','path':['flag']},'operator':operator,'value':expected}},
        'children':[{'id':'text','type':'text','props':{'text':'CONDITIONAL_CONTENT'}}]}]}


@pytest.mark.parametrize('actual,expected,visible',[(False,0,False),(0,False,False),(None,None,True),('',None,False),(1,1.0,True),('1',1,False),(False,False,True)])
def test_condition_preserves_types(actual,expected,visible):
    for operator in ('eq','ne'):
        html=ReportLayoutService.render(conditional(expected,operator),{}, {'flag':actual})
        assert ('CONDITIONAL_CONTENT' in html)==(visible if operator=='eq' else not visible)


def test_hidden_section_skips_descendant_binding_but_missing_condition_fails():
    layout=conditional();layout['body'][0]['children'][0]['props']={'binding':{'source':'data','path':['missing']}}
    assert 'CONDITIONAL_CONTENT' not in ReportLayoutService.render(layout,{}, {'flag':False})
    with pytest.raises(ReportError) as error:ReportLayoutService.render(layout,{}, {})
    assert error.value.code=='reports.error.binding'
    with pytest.raises(ReportError):ReportLayoutService.render(layout,{}, {'flag':True})
    with pytest.raises(ReportError):ReportLayoutService.render(conditional(),{}, {'flag':[]})


@pytest.mark.parametrize('spec',[None,{}, {'operator':'eval','binding':{'source':'data','path':['flag']},'value':1},
    {'operator':'eq','binding':{'source':'item','path':['flag']},'value':1},
    {'operator':'eq','binding':{'source':'data','path':['flag']},'value':[]},
    {'operator':'eq','binding':{'source':'data','path':['flag']},'value':float('nan')}])
def test_invalid_conditions(spec):
    layout=conditional();layout['body'][0]['props']['condition']=spec
    with pytest.raises(ReportError):ReportLayoutService.validate(layout)


def table(kind='sum'):
    return {'schema_version':1,'body':[{'id':'table','type':'table','props':{'collection':{'source':'data','path':['items']},
        'columns':[{'label':'Valor','binding':{'source':'item','path':['value']},'format':{'kind':'currency','null_text':'—'},'aggregate':kind}]}}]}


@pytest.mark.parametrize('kind,expected',[('sum','R$ 0,30'),('avg','R$ 0,15'),('min','R$ 0,10'),('max','R$ 0,20'),('count','3')])
def test_footer_decimal_and_null(kind,expected):
    html=ReportLayoutService.render(table(kind),{'items':[{'value':0.1},{'value':'0.2'},{'value':None}]},{})
    footer=html.split('<tfoot>')[1].split('</tfoot>')[0]
    assert expected in footer
    assert html.count('<tfoot>')==1
    assert 'tfoot { display:table-row-group;' in html


@pytest.mark.parametrize('kind,expected',[('sum','R$ 0,00'),('avg','—'),('min','—'),('max','—'),('count','0')])
def test_empty_collection_totals(kind,expected):
    assert expected in ReportLayoutService.render(table(kind),{'items':[]},{}).split('<tfoot>')[1]


@pytest.mark.parametrize('value',[True,'NaN','Infinity','1e100','1.234,56',{},[]])
def test_aggregate_rejects_bad_numbers(value):
    with pytest.raises(ValueError):aggregate([value],'sum')


def test_invalid_aggregate_and_escaped_raw_footer():
    for kind in ('eval',None,{},True):
        with pytest.raises(ReportError):ReportLayoutService.validate(table(kind))
    layout=table('avg');layout['body'][0]['props']['columns'][0]['format']={'null_text':'<script>'}
    html=ReportLayoutService.render(layout,{'items':[]},{})
    assert '&lt;script&gt;' in html and '<script>' not in html
    with pytest.raises(ReportError) as error:ReportLayoutService.render(table(),{'items':[{'value':'bad'}]}, {})
    assert error.value.code in ('reports.error.format','reports.error.aggregate')


def test_calculations_persist_publish_clone_and_snapshot(client):
    obj=create(client);value=read(client,obj['id']);value['layout']=table();value['layout']['body'][0]['props']['condition']={
        'binding':{'source':'parameters','path':['flag']},'operator':'eq','value':True}
    value['data_schema']={'type':'object','properties':{'items':{'type':'array'}},'required':['items']}
    value['sample_data']={'items':[{'value':0.1},{'value':0.2}]}
    value['parameters']=[{'key':'flag','label':'Exibir','schema':{'type':'boolean'},'default':True,'required':True}]
    assert save(client,obj['id'],value).status_code==200
    preview=post(client,f"/templates/{obj['id']}/versions/1/preview",{'format':'html','parameters':{}})
    assert preview.status_code==200 and 'R$ 0,30' in preview.json['html']
    assert post(client,f"/templates/{obj['id']}/versions/1/publish",{'lock_version':2}).status_code==200
    response=post(client,'/blocks',{'key':'totals.'+uuid.uuid4().hex,'name':'Totais','template_id':obj['id'],'version':1,'node_id':'table'})
    assert response.status_code==201
    block=response.json['item']
    assert client.get('/api/reports/blocks/'+str(block['id'])).json['item']['node']==value['layout']['body'][0]
    assert post(client,f"/templates/{obj['id']}/versions/1/clone",{}).status_code==201
    assert read(client,obj['id'],2)['layout']==value['layout']
    assert read(client,obj['id'])['status']=='published'
