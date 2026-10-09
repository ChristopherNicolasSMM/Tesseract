"""Organização dentro da cotação e propagação, sem reatribuir histórico."""
import json
import subprocess
from pathlib import Path
import pytest
from tests.test_addon_estoque import (app,client,_login_admin,_criar_processo_cotacao,_criar_cotacao,
    _criar_material,_criar_unidade,_criar_item_processo_cotacao,_criar_item_cotacao)
from tests.test_organization_stock import finance
from core.db import db
from addons.addon_estoque.root.services.purchase_context_service import bind_context,get_context
from addons.addon_estoque.root.services import estoque_service as stock
from addons.addon_estoque.root.model.processo_cotacao import ProcessoCotacao


def test_organization_area_initial_selection_readonly_and_generated_order(app,client):
    _login_admin(app,client)
    with app.app_context():
        finance('ORG_REAL');process=_criar_processo_cotacao();ident=process.id
    path=f'/estoque/processo-cotacaos/{ident}/organizacao-cotacao'
    initial=client.get(path)
    assert initial.status_code==200
    assert 'ORG_REAL' in initial.json['html'] and 'name="organization_code"' in initial.json['modal_html']
    assert initial.json['data'] is None
    assert client.post(path,json={'organization_code':'ORG_REAL'}).status_code==201
    bound=client.get(path)
    assert bound.json['data']['organization_code']=='ORG_REAL'
    assert 'name="organization_code"' not in bound.json['html']
    with app.app_context():
        process=db.session.get(ProcessoCotacao,ident)
        material=_criar_material();unit=_criar_unidade(material,'PCT',25)
        requested=_criar_item_processo_cotacao(process,material,unit)
        quote=_criar_cotacao(process);item=_criar_item_cotacao(quote,requested)
        stock.selecionar_item_cotacao_vencedor(item.id)
        result=stock.gerar_pedidos_de_cotacao(ident,actor='admin')
        assert get_context('order',result['pedidos_gerados'][0]['id']).organization_code=='ORG_REAL'


def test_explicit_binding_of_existing_draft_quotes_does_not_assign_currency_or_stock(app):
    from addons.addon_estoque.root.model.purchase_pricing import PurchasePricing
    from addons.addon_estoque.root.model.organization_stock import OrganizationMovement
    with app.app_context():
        finance();process=_criar_processo_cotacao();quote=_criar_cotacao(process)
        result=bind_context('process',process.id,{'organization_code':'A'},actor='admin')
        assert result.success,result.error
        assert quote.processo_cotacao_id==process.id and get_context('process',process.id).organization_code=='A'
        assert PurchasePricing.query.count()==OrganizationMovement.query.count()==0


@pytest.mark.parametrize('status',['enviada','respondida','recusada'])
def test_non_draft_quotes_cannot_receive_new_organization(app,status):
    with app.app_context():
        finance();process=_criar_processo_cotacao();_criar_cotacao(process,status=status)
        result=bind_context('process',process.id,{'organization_code':'A'},actor='admin')
        assert result.code==422 and get_context('process',process.id) is None


def test_selected_draft_response_cannot_be_reassigned_to_an_organization(app):
    with app.app_context():
        finance();process=_criar_processo_cotacao();material=_criar_material();unit=_criar_unidade(material,'PCT',25)
        requested=_criar_item_processo_cotacao(process,material,unit);quote=_criar_cotacao(process)
        item=_criar_item_cotacao(quote,requested);stock.selecionar_item_cotacao_vencedor(item.id)
        assert bind_context('process',process.id,{'organization_code':'A'},actor='admin').code==422


def test_organization_area_requires_authentication_and_reports_invalid_code(app,client):
    with app.app_context():
        finance();process=_criar_processo_cotacao();ident=process.id
    path=f'/estoque/processo-cotacaos/{ident}/organizacao-cotacao'
    assert client.get(path).status_code in (401,302)
    _login_admin(app,client)
    response=client.post(path,json={'organization_code':'MISSING'})
    assert response.status_code==422 and not response.json['success']
    with app.app_context():assert get_context('process',ident) is None


def test_real_js_mounts_organization_inside_quotation_and_preserves_selection_on_error():
    script=(Path(__file__).resolve().parents[1]/'static/js/estoque/processo_cotacao_detalhe.js').read_text(encoding='utf-8')
    component=script[script.index('  function initQuotationOrganization(config)'):script.index('  // ═══ Itens Pedidos')]
    harness=r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const component=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const slots=[],calls=[],parentSlots=[];let fail=false;
const document={querySelector:()=>({prepend:slot=>parentSlots.push(slot)}),createElement:()=>{
 const slot={innerHTML:'',listeners:{},addEventListener:(name,fn)=>slot.listeners[name]=fn};slots.push(slot);return slot;}};
const TesseractData={aviso:()=>{},_json:async(path,options)=>{
 calls.push({path,options});if(options){if(fail)throw new Error('Código inválido');return {success:true};}
 return {data:calls.some(c=>c.options)?{organization_code:'REAL'}:null,html:'header',modal_html:'modal'};}};
const context={document,TesseractData};
vm.runInNewContext('let quotationOrganization=null;'+component+'\ninitQuotationOrganization({processoCotacaoId:9});',context);
(async()=>{
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(parentSlots.length,2);assert.equal(slots[0].innerHTML,'header');assert.equal(slots[1].innerHTML,'modal');
 const button={disabled:false};const error={textContent:'',classList:{add:()=>{},remove:()=>{}}};
 const form={elements:{organization_code:{value:'REAL'}},querySelector:s=>s==='button'?button:error};
 fail=true;await slots[1].listeners.submit({preventDefault:()=>{},target:{closest:()=>form}});
 assert.equal(error.textContent,'Código inválido');assert.equal(form.elements.organization_code.value,'REAL');assert.equal(button.disabled,false);
 fail=false;await slots[0].listeners.submit({preventDefault:()=>{},target:{closest:()=>form}});
 assert.deepEqual(JSON.parse(calls.find(c=>c.options).options.body),{organization_code:'REAL'});
 assert.equal(vm.runInNewContext('quotationOrganization.organization_code',context),'REAL');
 console.log('Área organizacional da cotação aprovada');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    result=subprocess.run(['node','-e',harness],input=json.dumps(component),text=True,encoding='utf-8',capture_output=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert 'cotação aprovada' in result.stdout


def test_real_quote_invitation_js_requires_confirmed_organization():
    script=(Path(__file__).resolve().parents[1]/'static/js/estoque/processo_cotacao_detalhe.js').read_text(encoding='utf-8')
    component=script[script.index('  function initAbaCotacoes(config)'):script.index('  function abrirModalResponderPrecos')]
    harness=r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const component=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let save;const created=[];
const supplier={value:'1'};const error={textContent:'',classList:{add:()=>{},remove:()=>{}}};
const modal={querySelector:s=>s.includes("fornecedor_id")?supplier:s.includes('erro-cotacao')?error:
 s.includes('salvar-cotacao')?{addEventListener:(name,fn)=>save=fn}:{value:'',classList:{add:()=>{}}}};
const table={dataset:{}};const tbody={innerHTML:''};
const document={getElementById:()=>modal,querySelector:s=>s.includes('table[data-datatable]')?table:
 s.includes('tabela-cotacoes')?tbody:{addEventListener:()=>{}},addEventListener:()=>{}};
const TesseractData={esc:s=>String(s),aviso:()=>{},_json:async()=>({items:[]}),rest:{criar:async(base,data)=>created.push(data)}};
const context={document,TesseractData,window:{}};
vm.runInNewContext('let quotationOrganization=null;'+component+'\ninitAbaCotacoes({processoCotacaoId:9,apiBaseCotacoes:"quotes"});',context);
(async()=>{
 await save();assert.equal(created.length,0);assert.ok(error.textContent.includes('organização'));
 vm.runInNewContext('quotationOrganization={organization_code:"REAL"};',context);
 await save();assert.equal(created.length,1);assert.equal(created[0].processo_cotacao_id,9);
 console.log('Convite exige organização confirmada');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    result=subprocess.run(['node','-e',harness],input=json.dumps(component),text=True,encoding='utf-8',capture_output=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert 'organização confirmada' in result.stdout
