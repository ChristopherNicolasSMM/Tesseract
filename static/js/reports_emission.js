/* Emissão contextual: contratos publicados e filtros validados no servidor. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id),config=JSON.parse($('emission-config').textContent);
  const endpoint='/api/reports/emission/'+config.screen;
  let templates=[],busy=false;
  const status=message=>{$('emission-status').textContent=message;};
  function select(element,items,blank='Todos') {
    element.replaceChildren(new Option(blank,''));
    items.forEach(item=>element.add(new Option(item.label,JSON.stringify(item.value))));element.disabled=false;
  }
  function invalidate() {window.TesseractReportsPreview.clear($('emission-preview'),$('emission-print'));$('emission-preview-panel').hidden=true;}
  function parameters() {
    invalidate();const selected=templates.find(v=>v.key===$('emission-template').value);
    $('emission-parameters-json').value='{}';window.TesseractReportsParameters.mount($('emission-parameters'),selected?.parameters||[],$('emission-parameters-json'),{error:'Valor inválido',advanced_parameters:'Preencha o JSON',supply_parameter:'Informar parâmetro',choose:'Selecione',yes:'Sim',no:'Não',null_value:'Não informado',parameter_default:'Padrão'},invalidate);
  }
  async function start() {
    try {
      const response=await fetch(endpoint,{headers:{Accept:'application/json'}}),value=await response.json();
      if(!response.ok)throw Error(value.error?.message||'Não foi possível carregar os filtros.');
      templates=value.item.templates;
      if($('emission-record')) {
        select($('emission-record'),value.item.records,'Selecione');
        const match=value.item.records.find(row=>Object.keys(row.value).every(k=>String(row.value[k])===config.initial[k]));
        if(match)$('emission-record').value=JSON.stringify(match.value);
      }
      Object.entries(value.item.filters).forEach(([field,items])=>{if($('emission-'+field))select($('emission-'+field),items);});
      $('emission-template').replaceChildren(new Option('Selecione',''));
      templates.forEach(row=>$('emission-template').add(new Option(row.name+' · v'+row.version,row.key)));
      $('emission-template').disabled=!templates.length;$('emission-generate').disabled=!templates.length;
      if(templates.length===1)$('emission-template').value=templates[0].key;
      const wanted=config.initial.model==='checklist'?'ready.checklist-receita':null;
      if(wanted&&templates.some(v=>v.key===wanted))$('emission-template').value=wanted;
      parameters();status(templates.length?'Selecione os filtros e gere a prévia.':'Nenhum modelo compatível publicado. Crie e publique um modelo na IDE de Relatórios.');
    } catch(error) {status(error.message);}
  }
  $('emission-template').onchange=parameters;
  $('report-emission-form').addEventListener('input',invalidate);
  $('report-emission-form').addEventListener('change',invalidate);
  $('emission-print').onclick=()=>window.TesseractReportsPreview.print($('emission-preview'));
  $('report-emission-form').onsubmit=async event=>{
    event.preventDefault();if(busy)return;
    busy=true;const controls=Array.from($('report-emission-form').querySelectorAll('input,select,textarea,button')).map(element=>[element,element.disabled]);controls.forEach(([element])=>element.disabled=true);invalidate();status('Gerando relatório…');
    try {
      const selected=templates.find(v=>v.key===$('emission-template').value);if(!selected)throw Error('Selecione um modelo.');
      const options=$('emission-record')?JSON.parse($('emission-record').value):{},filters={};
      if(config.screen==='estoque'&&$('emission-material').value)options.material_id=Number($('emission-material').value);
      if(config.screen==='disponibilidade-validade'){options.days=Number($('emission-days').value);if($('emission-reference').value)options.reference_date=$('emission-reference').value;}
      config.fields.forEach(field=>{const element=$('emission-'+field);if(field==='positive_only'){filters[field]=element.checked;}else if(element.value){filters[field]=element.tagName==='SELECT'?JSON.parse(element.value):element.value.trim();}});
      const parameters=JSON.parse($('emission-parameters-json').value);
      const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json','X-Reports-CSRF':config.csrf},body:JSON.stringify({template:selected.key,version:selected.version,options,filters,parameters,format:'html'})});
      if(!response.ok){const value=await response.json();throw Error(value.error?.message||'Falha ao gerar relatório.');}
      $('emission-preview-panel').hidden=false;await window.TesseractReportsPreview.show($('emission-preview'),await response.text(),$('emission-print'));status('Prévia atualizada.');
    } catch(error){status(error.message);}finally{controls.forEach(([element,disabled])=>{if(element.id!=='emission-print')element.disabled=disabled;});busy=false;$('emission-generate').disabled=!templates.length;}
  };
  start();
})();
