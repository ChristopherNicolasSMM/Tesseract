"""Raster incorporado: validação de bytes, orçamento, revisão e entrega segura."""
import base64
from io import BytesIO
import random
import pytest
from PIL import Image
from addons.addon_reports.root.services.report_image_service import decode_image
from addons.addon_reports.root.services.report_layout_service import ReportLayoutService, ReportError
from addons.addon_reports.root.services.report_pdf_worker import blocked_fetcher
from tests.test_reports_workspace import app, client, create, read, save, post


def source(fmt='PNG', size=(8, 4), noise=False):
    image = Image.frombytes('RGB', size, random.Random(0).randbytes(size[0]*size[1]*3)) if noise else Image.new('RGB', size, '#336699')
    data = BytesIO()
    image.save(data, format=fmt)
    return 'data:image/'+('jpeg' if fmt=='JPEG' else fmt.lower())+';base64,'+base64.b64encode(data.getvalue()).decode('ascii')


def document(src=None, **props):
    return {'schema_version':1,'body':[{'id':'logo','type':'image','props':{'source':src or source(),'alt':'Logo <empresa>', **props}}]}


@pytest.mark.parametrize('fmt', ['PNG', 'JPEG'])
def test_valid_raster_and_worker(fmt):
    src = source(fmt)
    raw, mime = decode_image(src)
    fetched = blocked_fetcher(src)
    assert fetched == {'string':raw,'mime_type':mime}
    html = ReportLayoutService.render(document(src, width=50, height=20, style={'align':'right'}), {}, {})
    assert 'alt="Logo &lt;empresa&gt;"' in html
    assert 'width:50mm;max-width:100%;height:20mm;object-fit:contain;' in html
    assert 'text-align:right' in html and 'img-src data:' in html


@pytest.mark.parametrize('src', ['https://example.com/a.png','file:///tmp/a.png','data:image/svg+xml;base64,PHN2Zz4=','data:text/html;base64,PHNjcmlwdD4=', 'data:image/png;base64,?', 'data:image/png;base64,AA=='])
def test_reject_non_raster_sources(src):
    with pytest.raises(ReportError) as error:
        ReportLayoutService.validate(document(src))
    assert error.value.code == 'reports.error.image'
    with pytest.raises(ValueError):
        blocked_fetcher(src)


@pytest.mark.parametrize('props', [{'width':True},{'width':4},{'width':181},{'width':'40'},{'height':251},{'height':0},{'height':None},{'alt':'a'*241},{'alt':False},{'url':'https://example.com'},{'source':None}])
def test_reject_invalid_properties(props):
    value = document()
    value['body'][0]['props'].update(props)
    with pytest.raises(ReportError):
        ReportLayoutService.validate(value)


@pytest.mark.parametrize('src', [source('GIF'),source('JPEG').replace('image/jpeg','image/png'),source(size=(2049,1)),source(size=(2000,2001))])
def test_reject_format_mismatch_and_resolution(src):
    with pytest.raises(ValueError):
        decode_image(src)


def test_reject_truncated_raster_and_oversized_payload():
    for fmt in ('PNG','JPEG'):
        src = source(fmt)
        prefix, encoded = src.split(',',1)
        raw = base64.b64decode(encoded)
        with pytest.raises(ValueError):
            decode_image(prefix+','+base64.b64encode(raw[:len(raw)//2]).decode('ascii'))
    with pytest.raises(ValueError):
        decode_image('data:image/png;base64,'+base64.b64encode(b'x'*(128*1024+1)).decode('ascii'))


def test_reject_animation():
    data = BytesIO()
    Image.new('RGB',(2,2),'red').save(data,format='PNG',save_all=True,append_images=[Image.new('RGB',(2,2),'blue')],duration=100,loop=0)
    with pytest.raises(ValueError):
        decode_image('data:image/png;base64,'+base64.b64encode(data.getvalue()).decode('ascii'))


def test_total_budget_and_image_count():
    value = document(source(size=(200,200), noise=True))
    node = value['body'][0]
    value['body'] = [dict(node,id=str(index)) for index in range(4)]
    ReportLayoutService.validate(value)
    value['body'].append(dict(node,id='4'))
    with pytest.raises(ReportError):
        ReportLayoutService.validate(value)
    value = document()
    node = value['body'][0]
    value['body'] = [dict(node,id=str(index)) for index in range(16)]
    ReportLayoutService.validate(value)
    value['body'].append(dict(node,id='16'))
    with pytest.raises(ReportError):
        ReportLayoutService.validate(value)


def test_image_in_columns_persists_publish_clone_and_delivers(client):
    obj=create(client)
    value=read(client,obj['id'])
    original=document(width=60)
    value['layout']={'schema_version':1,'body':[{'id':'columns','type':'section','props':{'columns':2},'children':original['body']}]}
    assert save(client,obj['id'],value).status_code==200
    assert post(client,f"/templates/{obj['id']}/versions/1/publish",{'lock_version':2}).status_code==200
    response=post(client,'/render',{'template':obj['key'],'data':{},'parameters':{},'format':'html'})
    assert response.status_code==200
    assert 'img-src data:' in response.headers['Content-Security-Policy']
    assert original['body'][0]['props']['source'] in response.get_data(as_text=True)
    assert save(client,obj['id'],read(client,obj['id'])).status_code==409
    assert post(client,f"/templates/{obj['id']}/versions/1/clone",{}).status_code==201
    assert read(client,obj['id'],2)['layout']==value['layout']


def test_invalid_image_save_preserves_revision(client):
    obj=create(client)
    value=read(client,obj['id'])
    value['layout']=document()
    assert save(client,obj['id'],value).status_code==200
    original=read(client,obj['id'])
    replacement=read(client,obj['id'])
    replacement['layout']['body'][0]['props']['source']='https://example.com/logo.png'
    response=save(client,obj['id'],replacement)
    assert response.status_code==422
    assert response.json['error']['code']=='reports.error.image'
    assert response.json['error']['path']=='logo'
    current=read(client,obj['id'])
    assert current['lock_version']==original['lock_version']
    assert current['layout']==original['layout']
