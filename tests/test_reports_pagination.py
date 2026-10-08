"""Página, fragmentação e compatibilidade sem motor nativo obrigatório."""
import pytest
from addons.addon_reports.root.services.report_layout_service import ReportLayoutService, ReportError
from tests.test_reports_workspace import app, client, create, read, save, post


def document():
    return {'schema_version':1,'body':[{'id':'title','type':'text','props':{'text':'Página'}}]}


@pytest.mark.parametrize('page', [None,[],True,{'format':'evil'},{'orientation':'sideways'},{'margin_top':True},{'margin_left':-1},{'margin_bottom':41},{'margin_right':1.5},{'css':'url(x)'},{'format':['A4']},{'number_pages':1},{'number_pages':True,'margin_bottom':0}])
def test_invalid_page_rejected(page):
    value=document();value['page']=page
    with pytest.raises(ReportError) as error:ReportLayoutService.validate(value)
    assert error.value.code=='reports.error.page'


@pytest.mark.parametrize('format,width,height', [('A4',297,210),('A5',210,148),('Letter',279.4,215.9)])
def test_page_css_and_screen_dimensions(format,width,height):
    value=document();value['page']={'format':format,'orientation':'landscape','margin_top':0,'margin_right':10,'margin_bottom':20,'margin_left':30}
    html=ReportLayoutService.render(value,{}, {})
    assert f'@page {{ size: {format} landscape; margin: 0mm 10mm 20mm 30mm; }}' in html
    assert f'max-width:{width:g}mm; min-height:{height:g}mm;' in html


def test_legacy_page_defaults_unchanged():
    assert '@page { size: A4; margin: 15mm; }' in ReportLayoutService.render(document(),{}, {})


@pytest.mark.parametrize('pagination', [None,[],{'break_before':'page'},{'keep_together':1},{'css':'url(x)'}])
def test_invalid_pagination_rejected(pagination):
    value=document();value['body'][0]['props']['pagination']=pagination
    with pytest.raises(ReportError) as error:ReportLayoutService.validate(value)
    assert error.value.code=='reports.error.pagination'


def test_forced_breaks_and_keep_together_render():
    value=document();value['body'][0]['props']['pagination']={'break_before':True,'break_after':True,'keep_together':True}
    html=ReportLayoutService.render(value,{}, {})
    assert '<p style="break-before:page;break-after:page;break-inside:avoid">Página</p>' in html


@pytest.mark.parametrize('child', [{'id':'break','type':'page_break','props':{}}, {'id':'text','type':'text','props':{'text':'Texto','pagination':{'break_before':True}}}])
def test_forced_break_in_nested_column_rejected(child):
    value={'schema_version':1,'body':[{'id':'columns','type':'section','props':{'columns':2},'children':[{'id':'nested','type':'section','props':{},'children':[child]}]}]}
    with pytest.raises(ReportError) as error:ReportLayoutService.validate(value)
    assert error.value.code=='reports.error.pagination' and error.value.path==child['id']


def test_grid_container_break_is_allowed_and_page_settings_persist(client):
    obj=create(client);value=read(client,obj['id'])
    value['layout']={'schema_version':1,'page':{'format':'A5','orientation':'landscape','margin_top':0},'body':[{'id':'columns','type':'section','props':{'columns':2,'pagination':{'break_before':True,'keep_together':True}},'children':document()['body']}]}
    assert save(client,obj['id'],value).status_code==200
    preview=post(client,f"/templates/{obj['id']}/versions/1/preview",{})
    assert 'A5 landscape' in preview.json['html']
    assert 'break-before:page;break-inside:avoid' in preview.json['html']
    assert post(client,f"/templates/{obj['id']}/versions/1/publish",{'lock_version':2}).status_code==200
    assert post(client,f"/templates/{obj['id']}/versions/1/clone",{}).status_code==201
    assert read(client,obj['id'],2)['layout']==value['layout']


def test_page_numbering_css_is_optional():
    value=document()
    assert '@bottom-right' not in ReportLayoutService.render(value,{}, {})
    value['page']={'number_pages':True,'margin_bottom':8}
    assert 'counter(page)' in ReportLayoutService.render(value,{}, {})
