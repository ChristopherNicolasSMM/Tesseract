/* IDE declarativa; controles seguem Bootstrap/NiceAdmin existentes. */
(() => {
  'use strict';
  const root = document.getElementById('reports-workspace'); if (!root) return;
  const tr = JSON.parse(document.getElementById('reports-translations').textContent);
  const $ = id => document.getElementById(id);
  const layout=window.TesseractReportsLayout, blocks=new Map();
  const find=id=>layout.locate(revision.layout.body,id);
  let templateId, revision, selected, parameterScope, dirty = false, busy = false;
  const say = (key, state=key) => { $('report-status').textContent = tr[key] || key; $('report-status').dataset.state = state; };
  const mark = () => { dirty=true; say('dirty'); window.TesseractReportsPreview.clear($('html-preview'), $('print-report')); };
  const notify = error => { const message=(error.message || tr.error)+(error.reportPath?' · '+error.reportPath:'');if(revision && find(error.reportPath)){selected=error.reportPath;renderTree();}say(message,'error'); window.__tesseractToast?.show(message,'error'); };
  async function api(path, body, method='POST') {
    const response = await fetch('/api/reports'+path, {method, headers:{'Content-Type':'application/json','X-Reports-CSRF':root.dataset.csrf}, ...(body===undefined?{}:{body:JSON.stringify(body)})});
    if (response.ok && response.headers.get('Content-Type')?.includes('application/pdf')) return response.blob();
    const value = await response.json(); if (!response.ok) {const error=Error(value.error?.message || tr.error);error.reportPath=value.error?.path;throw error;} return value;
  }
  const path = () => `/templates/${templateId}/versions/${revision.version}`;
  const defs = () => JSON.parse($('parameter-definitions').value);
  const params = () => JSON.parse($('parameter-values').value);
  async function guarded(fn) { if(busy)return; busy=true; const controls=Array.from(root.querySelectorAll('input,textarea,select,button')).map(el=>[el,el.disabled]);controls.forEach(([el])=>el.disabled=true);try{await fn();}catch(e){notify(e instanceof SyntaxError?Error(tr.error):e);}finally{controls.forEach(([el,disabled])=>{if(el.isConnected)el.disabled=disabled;});if(revision){$('version-select').disabled=false;['data-schema','sample-data','parameter-definitions'].forEach(id=>$(id).disabled=revision.status!=='draft');renderTree();}busy=false;} }
  function applyStyle(element, style={}) {
    const names={align:'textAlign',font_size:'fontSize',bold:'fontWeight',margin_top:'marginTop',margin_bottom:'marginBottom',padding:'padding'};
    Object.entries(names).forEach(([key,name])=>{element.style[name]=style[key]===undefined?'':key==='align'?style[key]:key==='bold'?(style[key]?'700':'400'):style[key]+'pt';});
    element.style.setProperty('--report-cell-padding', (style.cell_padding ?? 6)+'pt');
  }
  function refreshVisual(node) {
    const block=blocks.get(node.id);
    const target=node.type==='table'?block.querySelector('table'):block;
    if(node.type==='section'){const children=block.querySelector(':scope > .report-section-children');if(children){children.style.display=node.props.columns>1?'grid':'';children.style.gridTemplateColumns=node.props.columns>1?`repeat(${node.props.columns},minmax(0,1fr))`:'';children.style.gap=node.props.columns>1?(node.props.gap??8)+'pt':'';}}
    if(node.type==='image'){const image=block.querySelector('img');image.style.width=(node.props.width??40)+'mm';image.style.height=node.props.height===undefined?'auto':node.props.height+'mm';image.style.objectFit='contain';}
    applyStyle(target,{...(node.type==='text'&&node.props.level==='title'?{font_size:18,bold:true}:node.type==='text'&&node.props.level==='subtitle'?{font_size:14,bold:true}:{}),...node.props.style});
    if(node.type==='table')node.props.columns.forEach((column,index)=>{
      const cell=block.querySelectorAll('th')[index];cell.style.width=column.width===undefined?'':column.width+'%';cell.style.textAlign=column.align||'';
    });
  }
  function selectProperty(label,id,value,options,update) {
    const wrapper=document.createElement('div');wrapper.className='mb-3';
    const title=document.createElement('label');title.className='form-label';title.htmlFor=id;title.textContent=label;
    const input=document.createElement('select');input.className='form-select';input.id=id;
    options.forEach(([key,text])=>{const option=document.createElement('option');option.value=key;option.textContent=text;input.append(option);});
    input.value=value;input.disabled=revision.status!=='draft';input.onchange=()=>{update(input.value);mark();};wrapper.append(title,input);$('node-properties').append(wrapper);
  }
  function formatProperties(target, prefix) {
    const options=['raw','number','currency','percent','date','datetime'].map(key=>[key,tr['format_'+key]]);
    const update=(key,value)=>{target.format={...target.format};if(value===undefined)delete target.format[key];else target.format[key]=value;};
    selectProperty(tr.format,prefix+'-kind',target.format?.kind||'raw',options,value=>{target.format={kind:value,...(target.format?.null_text===undefined?{}:{null_text:target.format.null_text})};mark();renderTree();});
    const kind=target.format?.kind||'raw';
    if(['number','currency','percent'].includes(kind)){
      const input=control(tr.decimals,prefix+'-decimals',target.format?.decimals??2,value=>{const number=Number(value);if(value===''||!Number.isInteger(number)||number<0||number>6)throw Error(tr.error);update('decimals',number);});input.type='number';input.min=0;input.max=6;input.step=1;
    }
    if(kind==='currency')selectProperty(tr.currency,prefix+'-currency',target.format?.currency||'BRL',['BRL','USD','EUR'].map(key=>[key,key]),value=>update('currency',value));
    control(tr.null_value,prefix+'-null',target.format?.null_text||'',value=>update('null_text',value));
  }
  function parameterForm() {
    try{window.TesseractReportsParameters.mount($('parameter-form'),defs(),$('parameter-values'),tr,()=>{window.TesseractReportsPreview.clear($('html-preview'),$('print-report'));});}catch(_){$('parameter-form').textContent=tr.error;}
  }
  function visualProperties(node) {
    if(node.type==='page_break')return;
    const heading=document.createElement('h3');heading.className='card-title';heading.textContent=tr.appearance;$('node-properties').append(heading);
    const update=(key,value)=>{node.props.style={...node.props.style};if(value===undefined)delete node.props.style[key];else node.props.style[key]=value;refreshVisual(node);};
    const options=[['',tr.automatic],...(node.type==='image'?['left','center','right']:['left','center','right','justify']).map(key=>[key,tr[key]])];
    selectProperty(tr.align,'style-align',node.props.style?.align||'',options,value=>update('align',value||undefined));
    if(node.type!=='image')selectProperty(tr.bold,'style-bold',node.props.style?.bold===undefined?'':String(node.props.style.bold),[['',tr.automatic],['true',tr.yes],['false',tr.no]],value=>update('bold',value===''?undefined:value==='true'));
    const ranges={font_size:[8,48],margin_top:[0,48],margin_bottom:[0,48],...(node.type==='table'?{cell_padding:[0,24]}:{padding:[0,24]})};
    Object.entries(ranges).forEach(([key,[min,max]])=>{
      if(node.type==='image'&&key==='font_size')return;
      const input=control(tr[key]+' (pt)','style-'+key,node.props.style?.[key]??'',value=>{
        if(value!==''&&(!Number.isInteger(Number(value))||Number(value)<min||Number(value)>max))throw Error(tr.error);
        update(key,value===''?undefined:Number(value));
      });input.type='number';input.min=min;input.max=max;input.step=1;
    });
    const reset=document.createElement('button');reset.type='button';reset.className='btn btn-sm btn-outline-secondary';reset.textContent=tr.reset_style;reset.disabled=revision.status!=='draft';reset.onclick=()=>{delete node.props.style;mark();renderTree();};$('node-properties').append(reset);
  }
  const pageDefaults={format:'A4',orientation:'portrait',number_pages:false,margin_top:15,margin_right:15,margin_bottom:15,margin_left:15};
  function renderPage() {
    const page={...pageDefaults,...revision.layout.page},dimensions={A4:[210,297],A5:[148,210],Letter:[215.9,279.4]}[page.format];
    const [width,height]=page.orientation==='landscape'?[...dimensions].reverse():dimensions;
    $('page-format').value=page.format;$('page-orientation').value=page.orientation;$('page-number-pages').checked=page.number_pages;$('page-margin-bottom').min=page.number_pages?8:0;
    ['top','right','bottom','left'].forEach(side=>$('page-margin-'+side).value=page['margin_'+side]);
    const paper=$('report-paper');paper.style.aspectRatio=width+'/'+height;paper.style.minHeight='0';paper.style.padding=['top','right','bottom','left'].map(side=>(page['margin_'+side]/width*100)+'%').join(' ');
  }
  function renderTree() {
    renderPage();
    $('report-tree').replaceChildren(); $('report-paper').replaceChildren();
    blocks.clear();
    function render(nodes,container,depth=0) {
      nodes.forEach(node=>{
        const tree=document.createElement('button');tree.type='button';tree.className='list-group-item list-group-item-action'+(node.id===selected?' active':'');
        tree.style.paddingInlineStart=(12+depth*14)+'px';tree.textContent=(tr[node.type]||node.type)+(node.type==='text'?' · '+(node.props.text||node.props.binding?.path.join('.')||'').slice(0,35):'');tree.setAttribute('aria-pressed',String(node.id===selected));
        tree.onclick=()=>{selected=node.id;renderTree();};$('report-tree').append(tree);
        const block=document.createElement(node.type==='section'?'div':'button');blocks.set(node.id,block);
        if(node.type==='section') {
          block.className='report-section';const header=document.createElement('button');header.type='button';header.textContent=tr.section;header.setAttribute('aria-pressed',String(node.id===selected));header.onclick=()=>{selected=node.id;renderTree();};block.append(header);
        } else {block.type='button';block.setAttribute('aria-pressed',String(node.id===selected));block.onclick=()=>{selected=node.id;renderTree();};}
        if(node.type==='text') {block.textContent=node.props.text ?? `${node.props.binding.source}.${node.props.binding.path.join('.')}`;if(node.props.level==='title')block.className='report-heading';}
        else if(node.type==='image') {const image=document.createElement('img');image.src=node.props.source;image.alt=node.props.alt||'';image.className='report-canvas-image';block.append(image);}
        else if(node.type==='table') {const table=document.createElement('table'),row=document.createElement('tr');node.props.columns.forEach(column=>{const cell=document.createElement('th');cell.textContent=column.label;row.append(cell);});table.append(row);block.append(table);}
        else if(node.type!=='section')block.textContent=tr[node.type]||node.type;
        container.append(block);refreshVisual(node);
        if(node.type==='section') {const children=document.createElement('div');children.className='report-section-children';block.append(children);render(node.children||[],children,depth+1);refreshVisual(node);}
      });
    }
    render(revision.layout.body,$('report-paper'));renderProperties();
    ['save-report','publish-report','add-text','add-table','add-divider','add-page_break','add-section','add-columns','add-image','report-image-file','duplicate-node','move-up','move-down','delete-node','load-example','report-example','page-format','page-orientation','page-number-pages','page-margin-top','page-margin-right','page-margin-bottom','page-margin-left','reset-page'].forEach(id=>$(id).disabled=revision.status!=='draft');
    $('add-page_break').disabled=revision.status!=='draft'||withinColumns(find(selected)?.node);
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
  function withinColumns(node) {while(node){if(node.type==='section'&&node.props.columns>1)return true;node=find(node.id)?.parent;}return false;}
  function renderProperties() {
    $('node-properties').replaceChildren();const entry=find(selected),node=entry?.node;if(!node)return;
    const excluded=new Set(layout.flatten([node]).map(item=>item.node.id));
    selectProperty(tr.parent,'node-parent',entry.parent?.id||'',[['',tr.document],...layout.flatten(revision.layout.body).filter(item=>item.node.type==='section'&&!excluded.has(item.node.id)).map(item=>[item.node.id,tr.section+' · '+item.node.id.slice(-8)])],value=>{try{layout.reparent(revision.layout.body,node.id,value);renderTree();}catch(error){notify(Error(tr.error));renderTree();}});
    if(node.type==='image') {
      const hint=document.createElement('p');hint.className='small text-muted';hint.textContent=tr.image_hint;$('node-properties').append(hint);
      const label=document.createElement('label');label.className='form-label';label.htmlFor='image-replace-file';label.textContent=tr.image_file;
      const file=document.createElement('input');file.id='image-replace-file';file.type='file';file.accept='image/png,image/jpeg';file.className='form-control mb-3';file.disabled=revision.status!=='draft';file.onchange=()=>{const chosen=file.files[0];if(chosen)guarded(async()=>{node.props.source=await readImage(chosen);mark();});};$('node-properties').append(label,file);
      const alt=control(tr.image_alt,'image-alt',node.props.alt||'',value=>{node.props.alt=value;blocks.get(node.id).querySelector('img').alt=value;});alt.maxLength=240;
      [['width',5,180],['height',5,250]].forEach(([key,min,max])=>{const input=control(tr['image_'+key]+' (mm)','image-'+key,node.props[key]??(key==='width'?40:''),value=>{const number=Number(value);if(key==='height'&&value==='')delete node.props.height;else {if(value===''||!Number.isInteger(number)||number<min||number>max)throw Error(tr.image_error);node.props[key]=number;}refreshVisual(node);});input.type='number';input.min=min;input.max=max;input.step=1;});
    }
    if(node.type==='section') {
      selectProperty(tr.composition_columns,'section-columns',String(node.props.columns||1),[1,2,3,4].map(value=>[String(value),String(value)]),value=>{node.props.columns=Number(value);refreshVisual(node);});
      const gap=control(tr.composition_gap+' (pt)','section-gap',node.props.gap??8,value=>{const number=Number(value);if(value===''||!Number.isInteger(number)||number<0||number>24)throw Error(tr.error);node.props.gap=number;refreshVisual(node);});gap.type='number';gap.min=0;gap.max=24;gap.step=1;
    }
    if(node.type==='text') {
      const select=document.createElement('select');select.className='form-select mb-3';select.setAttribute('aria-label',tr.content);
      ['literal','field'].forEach(mode=>{const option=document.createElement('option');option.value=mode;option.textContent=tr[mode];select.append(option);});select.value=node.props.binding?'field':'literal';select.disabled=revision.status!=='draft';
      select.onchange=()=>{const style=node.props.style, format=node.props.format, pagination=node.props.pagination;node.props=select.value==='field'?{binding:fields()[0]||{source:'data',path:['name']},level:'body'}:{text:tr.text,level:'body'};if(style)node.props.style=style;if(format)node.props.format=format;if(pagination)node.props.pagination=pagination;mark();renderTree();};$('node-properties').append(select);
      if(node.props.binding) bindingPicker(tr.binding,'node-binding',node.props.binding,fields(),value=>{node.props.binding=value;});
      else control(tr.content,'node-text',node.props.text,value=>{node.props.text=value; blocks.get(node.id).textContent=value;});
      formatProperties(node.props,'text-format');
      const level=document.createElement('select');level.className='form-select';level.setAttribute('aria-label',tr.level);['body','title','subtitle'].forEach(key=>{const option=document.createElement('option');option.value=key;option.textContent=tr[key];level.append(option);});level.value=node.props.level||'body';level.disabled=revision.status!=='draft';level.onchange=()=>{node.props.level=level.value;mark();renderTree();};$('node-properties').append(level);
    } else if(node.type==='table') {
      bindingPicker(tr.collection,'node-collection',node.props.collection,fields(null,true),value=>{node.props.collection=value;});
      let itemSchema;
      try { let schema=JSON.parse($('data-schema').value);for(const key of node.props.collection.path)schema=schema.properties?.[key];itemSchema=schema?.items; } catch(e){}
      node.props.columns.forEach((column,index)=>{
        control(tr.columns+' '+(index+1),'column-label-'+index,column.label,value=>{column.label=value;const block=blocks.get(node.id);block.querySelectorAll('th')[index].textContent=value;});
        bindingPicker(tr.binding,'column-binding-'+index,column.binding,fields(itemSchema),value=>{column.binding=value;});
        formatProperties(column,'column-format-'+index);
        selectProperty(tr.align,'column-align-'+index,column.align||'',[['',tr.automatic],...['left','center','right'].map(key=>[key,tr[key]])],value=>{if(value)column.align=value;else delete column.align;refreshVisual(node);});
        const width=control(tr.width+' (%)','column-width-'+index,column.width??'',value=>{
          const number=Number(value);if(value!==''&&(!Number.isInteger(number)||number<1||number>100))throw Error(tr.error);
          if(value==='')delete column.width;else column.width=number;refreshVisual(node);
        });width.type='number';width.min=1;width.max=100;width.step=1;
        const remove=document.createElement('button');remove.className='btn btn-sm btn-outline-danger mb-3';remove.textContent=tr.remove_column;remove.disabled=revision.status!=='draft'||node.props.columns.length<=1;remove.onclick=()=>{node.props.columns.splice(index,1);mark();renderTree();};$('node-properties').append(remove);
      });
      const add=document.createElement('button');add.className='btn btn-sm btn-outline-primary';add.textContent=tr.add_column;add.disabled=revision.status!=='draft'||node.props.columns.length>=12;add.onclick=()=>{node.props.columns.push({label:tr.content,binding:fields(itemSchema).find(f=>f.source==='item')||{source:'item',path:['name']}});mark();renderTree();};$('node-properties').append(add);
    }
    const panel=$('node-properties');
    function group(label,children) {if(!children.length)return;const details=document.createElement('details');details.open=true;details.className='report-property-group';const summary=document.createElement('summary');summary.className='fw-semibold mb-3';summary.textContent=label;details.append(summary,...children);panel.append(details);}
    group(tr.content,Array.from(panel.children).slice(1));
    if(node.type!=='page_break') {
      const before=panel.children.length;
      const insideColumns=withinColumns(entry.parent);
      ['break_before','break_after','keep_together'].forEach(key=>{selectProperty(tr[key],'pagination-'+key,String(node.props.pagination?.[key]||false),[['false',tr.no],['true',tr.yes]],value=>{node.props.pagination={...node.props.pagination,[key]:value==='true'};});if(insideColumns&&key!=='keep_together')$('pagination-'+key).disabled=true;});
      group(tr.pagination,Array.from(panel.children).slice(before));
    }
    const before=panel.children.length;visualProperties(node);
    const appearance=Array.from(panel.children).slice(before);if(appearance[0]?.tagName==='H3')appearance.shift().remove();group(tr.appearance,appearance);
  }
  async function load(number) {
    const scope=templateId+':'+number;if(parameterScope!==scope){$('parameter-values').value='{}';parameterScope=scope;}
    revision=(await api(`/templates/${templateId}/versions/${number}`,undefined,'GET')).item;dirty=false;selected=revision.layout.body[0]?.id;
    $('data-schema').value=JSON.stringify(revision.data_schema,null,2);$('sample-data').value=JSON.stringify(revision.sample_data,null,2);$('parameter-definitions').value=JSON.stringify(revision.parameters,null,2);
    ['data-schema','sample-data','parameter-definitions'].forEach(id=>$(id).disabled=revision.status!=='draft');
    parameterForm();
    window.TesseractReportsPreview.clear($('html-preview'), $('print-report'));
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
  ['text','table','divider','page_break','section'].forEach(type=>$('add-'+type).onclick=()=>{const node={id:'node_'+crypto.randomUUID(),type,props:type==='text'?{text:tr.text,level:'body'}:type==='table'?{collection:{source:'data',path:['items']},columns:[{label:tr.content,binding:{source:'item',path:['name']}}]}:{}};if(type==='section')node.children=[];const entry=find(selected);const destination=entry?.node.type==='section'?(entry.node.children||=[]):(entry?.siblings||revision.layout.body);destination.push(node);try{layout.validate(revision.layout.body);}catch(error){destination.pop();notify(Error(tr.error));return;}selected=node.id;mark();renderTree();});
  async function readImage(file) {
    if(!file.size||file.size>128*1024)throw Error(tr.image_error);
    const bytes=new Uint8Array(await file.arrayBuffer());
    const png=[137,80,78,71,13,10,26,10].every((value,index)=>bytes[index]===value),jpeg=bytes[0]===255&&bytes[1]===216&&bytes[2]===255;
    if(!png&&!jpeg)throw Error(tr.image_error);
    const mime=png?'image/png':'image/jpeg';
    const source=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve('data:'+mime+';base64,'+reader.result.split(',')[1]);reader.onerror=()=>reject(Error(tr.image_error));reader.readAsDataURL(file);});
    const image=new Image();image.src=source;try{await image.decode();}catch(error){throw Error(tr.image_error);}
    if(image.naturalWidth>2048||image.naturalHeight>2048||image.naturalWidth*image.naturalHeight>4000000)throw Error(tr.image_error);
    return source;
  }
  $('add-image').onclick=()=>{$('report-image-file').value='';$('report-image-file').click();};
  $('report-image-file').onchange=()=>{const file=$('report-image-file').files[0];if(!file)return;guarded(async()=>{const source=await readImage(file),node={id:'node_'+crypto.randomUUID(),type:'image',props:{source,alt:'',width:40}},entry=find(selected),destination=entry?.node.type==='section'?(entry.node.children||=[]):(entry?.siblings||revision.layout.body);destination.push(node);try{layout.validate(revision.layout.body);}catch(error){destination.pop();throw Error(tr.error);}selected=node.id;mark();});};
  $('add-columns').onclick=()=>{const node={id:'node_'+crypto.randomUUID(),type:'section',props:{columns:2,gap:8},children:[0,1].map(()=>({id:'node_'+crypto.randomUUID(),type:'section',props:{},children:[]}))};const entry=find(selected),destination=entry?.node.type==='section'?(entry.node.children||=[]):(entry?.siblings||revision.layout.body);destination.push(node);try{layout.validate(revision.layout.body);}catch(error){destination.pop();notify(Error(tr.error));return;}selected=node.id;mark();renderTree();};
  $('duplicate-node').onclick=()=>{try{const copy=layout.duplicate(revision.layout.body,selected);if(copy){selected=copy.id;mark();renderTree();}}catch(error){notify(Error(tr.error));}};
  $('delete-node').onclick=()=>{const entry=find(selected);if(!entry)return;layout.remove(revision.layout.body,selected);selected=entry.parent?.id||revision.layout.body[0]?.id;mark();renderTree();};
  [-1,1].forEach((delta,i)=>$(i?'move-down':'move-up').onclick=()=>{if(layout.move(revision.layout.body,selected,delta)){mark();renderTree();}});
  ['data-schema','parameter-definitions'].forEach(id=>$(id).onblur=()=>{renderProperties();if(id==='parameter-definitions')parameterForm();});
  ['data-schema','sample-data','parameter-definitions','parameter-values'].forEach(id=>$(id).oninput=()=>{if(id!=='parameter-values')mark();else { window.TesseractReportsPreview.clear($('html-preview'), $('print-report')); say('stale','dirty'); }});
  function guardedSave(fn) { if(!root.reportValidity()){notify(Error(tr.error));return;}return guarded(fn); }
  ['format','orientation'].forEach(key=>$('page-'+key).onchange=()=>{revision.layout.page={...pageDefaults,...revision.layout.page,[key]:$('page-'+key).value};mark();renderPage();});
  ['top','right','bottom','left'].forEach(side=>{const input=$('page-margin-'+side);input.oninput=()=>{const value=Number(input.value);if(input.value===''||!Number.isInteger(value)||value<0||value>40){input.setCustomValidity(tr.error);return;}input.setCustomValidity('');revision.layout.page={...pageDefaults,...revision.layout.page,['margin_'+side]:value};mark();renderPage();};});
  $('page-number-pages').onchange=()=>{revision.layout.page={...pageDefaults,...revision.layout.page,number_pages:$('page-number-pages').checked};mark();renderPage();};
  $('reset-page').onclick=()=>{delete revision.layout.page;['top','right','bottom','left'].forEach(side=>$('page-margin-'+side).setCustomValidity(''));mark();renderPage();};
  $('save-report').onclick=()=>guardedSave(save);
  $('load-example').onclick=()=>guarded(async()=>{
    if(revision.status!=='draft')return;
    if(!await window.__tesseractConfirm({key:'reports.confirm.example'}))return;
    const example=(await api('/examples/'+$('report-example').value,undefined,'GET')).item;
    revision.layout=example.layout;selected=revision.layout.body[0]?.id;
    $('data-schema').value=JSON.stringify(example.data_schema,null,2);
    $('sample-data').value=JSON.stringify(example.sample_data,null,2);
    $('parameter-definitions').value=JSON.stringify(example.parameters,null,2);
    $('parameter-values').value='{}';parameterForm();mark();renderTree();
  });
  $('preview-report').onclick=()=>guardedSave(async()=>{if(dirty)await save();const value=await api(path()+'/preview',{parameters:params(),format:'html'});bootstrap.Modal.getOrCreateInstance($('reports-preview')).show();await window.TesseractReportsPreview.show($('html-preview'),value.html,$('print-report'));say('preview');});
  $('print-report').onclick=()=>window.TesseractReportsPreview.print($('html-preview'));
  $('publish-report').onclick=()=>guardedSave(async()=>{if(dirty)await save();const ok=await window.__tesseractConfirm({key:'reports.confirm.publish'});if(!ok)return;await api(path()+'/publish',{lock_version:revision.lock_version,parameters:params()});await choose(revision.version);});
  $('clone-report').onclick=()=>guarded(async()=>{if(dirty)throw Error(tr.unsaved);const item=(await api(path()+'/clone',{})).item;await choose(item.version);});
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  const initial=new URL(location.href);if(initial.searchParams.has('template'))guarded(async()=>{templateId=initial.searchParams.get('template');$('template-select').value=templateId;await choose(Number(initial.searchParams.get('version'))||undefined);});
})();
