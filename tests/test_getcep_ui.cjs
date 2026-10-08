/* Teste de comportamento do script real, com DOM mínimo e rede controlada. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Element {
  constructor(name = '', value = '') { this.name=name; this.value=value; this.listeners={}; this.isConnected=true; this.disabled=false; this.readOnly=false; this.textContent=''; }
  addEventListener(name,fn) { (this.listeners[name] ||= []).push(fn); }
  dispatchEvent(event) { (this.listeners[event.type] || []).forEach(fn=>fn(event)); }
  setAttribute() {}
  closest(selector) { return selector === 'form' ? (this.formScope || scope) : null; }
  insertAdjacentElement(position,element) { created.push(element); }
}
const created=[];
const fields=Object.fromEntries(['cep','logradouro','bairro','cidade','estado','numero','complemento','pais'].map(name=>[name,new Element(name)]));
const scope={querySelector(selector){return fields[selector.match(/name="([^"]+)"/)[1]] || null;}};
const inputs=[fields.cep];
let rescan;
const requests=[];
const context={document:{currentScript:{dataset:{getcepUrl:'/tesseract/api/plugins/getcep/__CEP__'}},body:{},querySelectorAll(){return inputs;},createElement(){return new Element();}},
  MutationObserver:class{constructor(fn){rescan=fn;}observe(){}},WeakMap,AbortController,Event,setTimeout,clearTimeout,
  fetch(url,options){return new Promise(resolve=>requests.push({url,options,resolve}));}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../plugins/plugin_getcep/static/getcep.js'),'utf8'),context);
const [button,status]=created;
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const address={logradouro:'Praça da Sé',bairro:'Sé',cidade:'São Paulo',estado:'SP'};
function respond(index,result={success:true,address},ok=true){requests[index].resolve({ok,json:async()=>result});}
function blur(){fields.cep.dispatchEvent(new Event('blur'));}
function change(value){fields.cep.value=value;fields.cep.dispatchEvent(new Event('input'));}
async function run(){
  rescan();assert.equal(created.length,2,'não duplica controles após AJAX');
  change('01001-000');fields.numero.value='42';fields.complemento.value='Sala 2';blur();
  assert.equal(requests[0].url,'/tesseract/api/plugins/getcep/01001000');
  fields.bairro.value='Digitado durante consulta';respond(0);await tick();
  assert.equal(fields.cidade.value,'São Paulo');assert.equal(fields.bairro.value,'Digitado durante consulta');
  assert.equal(fields.numero.value,'42');assert.equal(fields.complemento.value,'Sala 2');
  assert.match(status.textContent,/preservados/);
  // Consulta antiga não pode aplicar o endereço de um CEP anterior.
  for(const name of ['logradouro','bairro','cidade','estado'])fields[name].value='';
  change('02002000');blur();change('03003000');blur();
  assert.equal(requests[1].options.signal.aborted,true);
  respond(2,{success:true,address:{...address,cidade:'Novo'}});await tick();
  respond(1,{success:true,address:{...address,cidade:'Antigo'}});await tick();
  assert.equal(fields.cidade.value,'Novo');
  // Falha de API não limpa endereço nem bloqueia a edição.
  change('04004000');button.dispatchEvent(new Event('click'));respond(3,{success:false,error:'falha'},false);await tick();
  assert.equal(fields.cidade.value,'Novo');assert.match(status.textContent,/manual/);
  // País estrangeiro e CEP inválido não acionam a API brasileira.
  fields.pais.value='Argentina';change('05005000');blur();assert.equal(requests.length,4);
  fields.pais.value='';change('a01001000');blur();assert.equal(requests.length,4);
  // País alterado durante a consulta invalida a resposta brasileira.
  fields.pais.value='Brasil';change('06006000');blur();fields.pais.value='Argentina';
  respond(4,{success:true,address:{...address,cidade:'Não aplicar'}});await tick();
  assert.equal(fields.cidade.value,'Novo');
  // O perfil Core usa campos endereco_*; mapear os nomes reais explicitamente.
  const profile=Object.fromEntries(['endereco_cep','endereco_rua','endereco_bairro','endereco_cidade','endereco_uf','endereco_numero','endereco_complemento'].map(name=>[name,new Element(name)]));
  profile.endereco_cep.formScope={querySelector(selector){return profile[selector.match(/name="([^"]+)"/)[1]] || null;}};
  profile.endereco_cep.value='01001000';inputs.push(profile.endereco_cep);rescan();assert.equal(created.length,4);
  profile.endereco_numero.value='7';profile.endereco_cep.dispatchEvent(new Event('blur'));respond(5);await tick();
  assert.equal(profile.endereco_rua.value,'Praça da Sé');assert.equal(profile.endereco_cidade.value,'São Paulo');assert.equal(profile.endereco_uf.value,'SP');assert.equal(profile.endereco_numero.value,'7');
  // CEP completo consulta após pausa, sem exigir blur ou clique.
  fields.pais.value='Brasil';fields.cidade.value='';change('07007000');
  await new Promise(resolve=>setTimeout(resolve,550));assert.equal(requests.length,7);respond(6);await tick();
  assert.equal(fields.cidade.value,'São Paulo');
  console.log('GetCEP UI: 7 cenários aprovados (preenchimento, corrida, falha, validação local, país, perfil Core, consulta automática/prefixo).');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
