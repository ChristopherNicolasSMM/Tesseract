/* IDE declarativa; controles seguem Bootstrap/NiceAdmin existentes. */
(() => {
  'use strict';
  const root = document.getElementById('reports-workspace'); if (!root) return;
  const tr = JSON.parse(document.getElementById('reports-translations').textContent);
  const $ = id => document.getElementById(id);
  let templateId, revision, selected, dirty = false, busy = false, pdfUrl;
  const say = (key, state=key) => { $('report-status').textContent = tr[key] || key; $('report-status').dataset.state = state; };
  const mark = () => { dirty=true; say('dirty'); if (pdfUrl) { URL.revokeObjectURL(pdfUrl); pdfUrl=null; $('pdf-preview').removeAttribute('src'); } };
  const notify = error => { const message=(error.message || tr.error)+(error.reportPath?' · '+error.reportPath:'');if(revision?.layout.body.some(node=>node.id===error.reportPath)){selected=error.reportPath;renderTree();}say(message,'error'); window.__tesseractToast?.show(message,'error'); };
  async function api(path, body, method='POST') {
    const response = await fetch('/api/reports'+path, {method, headers:{'Content-Type':'application/json','X-Reports-CSRF':root.dataset.csrf}, ...(body===undefined?{}:{body:JSON.stringify(body)})});
    if (response.ok && response.headers.get('Content-Type')?.includes('application/pdf')) return response.blob();
    const value = await response.json(); if (!response.ok) {const error=Error(value.error?.message || tr.error);error.reportPath=value.error?.path;throw error;} return value;
  }
  const path = () => `/templates/${templateId}/versions/${revision.version}`;
  const defs = () => JSON.parse($('parameter-definitions').value);
  const params = () => JSON.parse($('parameter-values').value);
  async function guarded(fn) { if(busy)return; busy=true; const controls=Array.from(root.querySelectorAll('input,textarea,select,button')).map(el=>[el,el.disabled]);controls.forEach(([el])=>el.disabled=true);try{await fn();}catch(e){notify(e instanceof SyntaxError?Error(tr.error):e);}finally{controls.forEach(([el,disabled])=>{if(el.isConnected)el.disabled=disabled;});if(revision){$('version-select').disabled=false;['data-schema','sample-data','parameter-definitions'].forEach(id=>$(id).disabled=revision.status!=='draft');renderTree();}busy=false;} }
  function renderTree() {
    $('report-tree').replaceChildren(); $('report-paper').replaceChildren();
    revision.layout.body.forEach(node=>{
      const tree=document.createElement('button'); tree.type='button'; tree.className='list-group-item list-group-item-action'+(node.id===selected?' active':''); tree.textContent=tr[node.type]||node.type; tree.onclick=()=>{selected=node.id;renderTree();}; $('report-tree').append(tree);
      const block=document.createElement('button'); block.type='button'; block.setAttribute('aria-pressed',String(node.id===selected)); block.onclick=()=>{selected=node.id;renderTree();};
      if(node.type==='text') { block.textContent=node.props.text ?? `${node.props.binding.source}.${node.props.binding.path.join('.')}`; if(node.props.level==='title')block.className='fs-3 fw-bold'; }
      else if(node.type==='table') { const table=document.createElement('table'), row=document.createElement('tr'); node.props.columns.forEach(c=>{const cell=document.createElement('th');cell.textContent=c.label;row.append(cell);});table.append(row);block.append(table); }
      else block.textContent=tr[node.type]||node.type;
      $('report-paper').append(block);
    }); renderProperties();
    ['save-report','publish-report','add-text','add-table','add-divider','move-up','move-down','delete-node','load-example','report-example'].forEach(id=>$(id).disabled=revision.status!=='draft');
  }
  function control(label, id, value, update, textarea=false) {
    const div=document.createElement('div');div.className='mb-3';const title=document.createElement('label');title.className='form-label';title.htmlFor=id;title.textContent=label;
    const input=document.createElement(textarea?'textarea':'input');input.id=id;input.className='form-control';input.value=value;if(textarea)input.rows=6;
    input.disabled=revision.status!=='draft';input.oninput=()=>{try{update(input.value);mark();input.setCustomValidity('');}catch(e){input.setCustomValidity(tr.error);}};div.append(title,input);$('node-properties').append(div);return input;
  }
  function schemaFields(schema, source, arraysOnly=false, path=[], result=[]) {
    if(!schema || typeof schema!=='object'||path.length>32)return result;
    if(path.length && (arraysOnly?schema.type==='array':schema.type!=='object'&&schema.type!=='array'))result.push({source,path});
    Object.entries(schema.properties||{}).forEach(([key,value])=>schemaFields(value,source,arraysOnly,[...path,key],result));
    return result;
  }
  function fields(itemSchema, arraysOnly=false) {
    let schema;try{schema=JSON.parse($('data-schema').value);}catch(e){return [];}
    const result=schemaFields(schema,'data',arraysOnly);
    if(itemSchema)schemaFields(itemSchema,'item',arraysOnly,[],result);
    if(!arraysOnly) { try{defs().forEach(d=>schemaFields(d.schema,'parameters',false,[d.key],result));}catch(e){} }
    return result;
  }
  function bindingPicker(label, id, binding, choices, update) {
    const div=document.createElement('div');div.className='mb-3';const title=document.createElement('label');title.className='form-label';title.htmlFor=id;title.textContent=label;
    const select=document.createElement('select');select.className='form-select';select.id=id;
    const current=JSON.stringify({source:binding?.source,path:binding?.path});let found=false;
    choices.forEach(choice=>{const option=document.createElement('option');option.value=JSON.stringify(choice);option.textContent=choice.source+'.'+choice.path.join('.');if(option.value===current)found=true;select.append(option);});
    if(!found){const option=document.createElement('option');option.value=current;option.textContent=(binding?.source||'data')+'.'+(binding?.path||[]).join('.')+' · '+tr.missing;select.prepend(option);}
    select.value=current;select.disabled=revision.status!=='draft';select.onchange=()=>{update({...binding,...JSON.parse(select.value)});mark();renderTree();};div.append(title,select);$('node-properties').append(div);
  }
  function renderProperties() {
    $('node-properties').replaceChildren();const node=revision.layout.body.find(n=>n.id===selected);if(!node)return;
    if(node.type==='text') {
      const select=document.createElement('select');select.className='form-select mb-3';select.setAttribute('aria-label',tr.content);
      ['literal','field'].forEach(mode=>{const option=document.createElement('option');option.value=mode;option.textContent=tr[mode];select.append(option);});select.value=node.props.binding?'field':'literal';select.disabled=revision.status!=='draft';
      select.onchange=()=>{node.props=select.value==='field'?{binding:fields()[0]||{source:'data',path:['name']},level:'body'}:{text:tr.text,level:'body'};mark();renderTree();};$('node-properties').append(select);
      if(node.props.binding) bindingPicker(tr.binding,'node-binding',node.props.binding,fields(),value=>{node.props.binding=value;});
      else control(tr.content,'node-text',node.props.text,value=>{node.props.text=value; const i=revision.layout.body.indexOf(node); $('report-paper').children[i].textContent=value;});
      const level=document.createElement('select');level.className='form-select';level.setAttribute('aria-label',tr.level);['body','title','subtitle'].forEach(key=>{const option=document.createElement('option');option.value=key;option.textContent=tr[key];level.append(option);});level.value=node.props.level||'body';level.disabled=revision.status!=='draft';level.onchange=()=>{node.props.level=level.value;mark();renderTree();};$('node-properties').append(level);
    } else if(node.type==='table') {
      bindingPicker(tr.collection,'node-collection',node.props.collection,fields(null,true),value=>{node.props.collection=value;});
      let itemSchema;
      try { let schema=JSON.parse($('data-schema').value);for(const key of node.props.collection.path)schema=schema.properties?.[key];itemSchema=schema?.items; } catch(e){}
      node.props.columns.forEach((column,index)=>{
        control(tr.columns+' '+(index+1),'column-label-'+index,column.label,value=>{column.label=value;const block=$('report-paper').children[revision.layout.body.indexOf(node)];block.querySelectorAll('th')[index].textContent=value;});
        bindingPicker(tr.binding,'column-binding-'+index,column.binding,fields(itemSchema),value=>{column.binding=value;});
        const remove=document.createElement('button');remove.className='btn btn-sm btn-outline-danger mb-3';remove.textContent=tr.remove_column;remove.disabled=revision.status!=='draft'||node.props.columns.length<=1;remove.onclick=()=>{node.props.columns.splice(index,1);mark();renderTree();};$('node-properties').append(remove);
      });
      const add=document.createElement('button');add.className='btn btn-sm btn-outline-primary';add.textContent=tr.add_column;add.disabled=revision.status!=='draft'||node.props.columns.length>=12;add.onclick=()=>{node.props.columns.push({label:tr.content,binding:fields(itemSchema).find(f=>f.source==='item')||{source:'item',path:['name']}});mark();renderTree();};$('node-properties').append(add);
    }
  }
  async function load(number) {
    revision=(await api(`/templates/${templateId}/versions/${number}`,undefined,'GET')).item;dirty=false;selected=revision.layout.body[0]?.id;
    $('data-schema').value=JSON.stringify(revision.data_schema,null,2);$('sample-data').value=JSON.stringify(revision.sample_data,null,2);$('parameter-definitions').value=JSON.stringify(revision.parameters,null,2);
    ['data-schema','sample-data','parameter-definitions'].forEach(id=>$(id).disabled=revision.status!=='draft');
    $('editor-panel').hidden=false;$('version-details').textContent=JSON.stringify({version:revision.version,status:revision.status,hash:revision.content_hash},null,2);say(revision.status==='draft'?'saved':'published');renderTree();
    const url=new URL(location.href);url.searchParams.set('template',templateId);url.searchParams.set('version',number);history.replaceState(null,'',url);
  }
  async function choose(number) {
    const versions=(await api(`/templates/${templateId}/versions`,undefined,'GET')).items;$('version-select').replaceChildren();versions.forEach(v=>{const option=document.createElement('option');option.value=v.version;option.textContent=`${v.version} · ${v.status==='draft'?tr.draft:tr.published}`;$('version-select').append(option);});$('version-select').disabled=false;const target=number||versions[0].version;$('version-select').value=target;await load(target);
  }
  async function save() {
    if(!root.reportValidity())throw Error(tr.error);
    say('saving');revision=(await api(path(),{lock_version:revision.lock_version,layout:revision.layout,data_schema:JSON.parse($('data-schema').value),sample_data:JSON.parse($('sample-data').value),parameters:defs()},'PUT')).item;dirty=false;say('saved');
  }
  root.reportValidity=()=>Array.from($('editor-panel').querySelectorAll('input,textarea,select')).every(el=>el.disabled||el.reportValidity());
  $('create-report').onsubmit=event=>{event.preventDefault();guarded(async()=>{if(dirty)throw Error(tr.unsaved);const item=(await api('/templates',{key:$('report-key').value,name:$('report-name').value})).item;const option=document.createElement('option');option.value=item.id;option.textContent=item.name;$('template-select').append(option);templateId=item.id;$('template-select').value=templateId;await choose(1);});};
  $('template-select').onchange=()=>guarded(async()=>{if(dirty){$('template-select').value=templateId;throw Error(tr.unsaved);}if(!$('template-select').value){$('editor-panel').hidden=true;templateId=undefined;revision=undefined;return;}templateId=$('template-select').value;await choose();});
  $('version-select').onchange=()=>guarded(async()=>{if(dirty){$('version-select').value=revision.version;throw Error(tr.unsaved);}await load(Number($('version-select').value));});
  ['text','table','divider'].forEach(type=>$('add-'+type).onclick=()=>{const node={id:'node_'+crypto.randomUUID(),type,props:type==='text'?{text:tr.text,level:'body'}:type==='table'?{collection:{source:'data',path:['items']},columns:[{label:tr.content,binding:{source:'item',path:['name']}}]}:{}};revision.layout.body.push(node);selected=node.id;mark();renderTree();});
  $('delete-node').onclick=()=>{revision.layout.body=revision.layout.body.filter(n=>n.id!==selected);selected=revision.layout.body[0]?.id;mark();renderTree();};
  [-1,1].forEach((delta,i)=>$(i?'move-down':'move-up').onclick=()=>{const index=revision.layout.body.findIndex(n=>n.id===selected),next=index+delta;if(index<0||next<0||next>=revision.layout.body.length)return;[revision.layout.body[index],revision.layout.body[next]]=[revision.layout.body[next],revision.layout.body[index]];mark();renderTree();});
  ['data-schema','parameter-definitions'].forEach(id=>$(id).onblur=()=>renderProperties());
  ['data-schema','sample-data','parameter-definitions','parameter-values'].forEach(id=>$(id).oninput=()=>{if(id!=='parameter-values')mark();else if(pdfUrl)say('stale','dirty');});
  $('save-report').onclick=()=>guarded(save);
  $('load-example').onclick=()=>guarded(async()=>{
    if(revision.status!=='draft')return;
    if(!await window.__tesseractConfirm({key:'reports.confirm.example'}))return;
    const example=(await api('/examples/'+$('report-example').value,undefined,'GET')).item;
    revision.layout=example.layout;selected=revision.layout.body[0]?.id;
    $('data-schema').value=JSON.stringify(example.data_schema,null,2);
    $('sample-data').value=JSON.stringify(example.sample_data,null,2);
    $('parameter-definitions').value=JSON.stringify(example.parameters,null,2);
    $('parameter-values').value='{}';mark();renderTree();
  });
  $('preview-report').onclick=()=>guarded(async()=>{if(dirty)await save();const blob=await api(path()+'/preview',{parameters:params()});if(pdfUrl)URL.revokeObjectURL(pdfUrl);pdfUrl=URL.createObjectURL(blob);$('pdf-preview').src=pdfUrl;bootstrap.Modal.getOrCreateInstance($('reports-preview')).show();say('preview');});
  $('publish-report').onclick=()=>guarded(async()=>{if(dirty)await save();const ok=await window.__tesseractConfirm({key:'reports.confirm.publish'});if(!ok)return;await api(path()+'/publish',{lock_version:revision.lock_version,parameters:params()});await choose(revision.version);});
  $('clone-report').onclick=()=>guarded(async()=>{if(dirty)throw Error(tr.unsaved);const item=(await api(path()+'/clone',{})).item;await choose(item.version);});
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  const initial=new URL(location.href);if(initial.searchParams.has('template'))guarded(async()=>{templateId=initial.searchParams.get('template');$('template-select').value=templateId;await choose(Number(initial.searchParams.get('version'))||undefined);});
})();
