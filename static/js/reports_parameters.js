/* Formulário de valores; o backend permanece autoridade do JSON Schema. */
(() => {
  'use strict';
  const listeners=new WeakMap();
  function mount(container, definitions, source, tr, changed) {
    const previous=listeners.get(source);if(previous)source.removeEventListener('input',previous);
    function draw() {
      container.replaceChildren();let values;
      try {values=JSON.parse(source.value);if(!values||Array.isArray(values)||typeof values!=='object')throw Error();}
      catch(_){container.textContent=tr.error;return;}
      definitions.forEach((definition,index)=>{
        const schema=definition.schema||{}, type=Array.isArray(schema.type)?schema.type.find(t=>t!=='null'):schema.type;
        const wrapper=document.createElement('div');wrapper.className='mb-3';
        const label=document.createElement('label');label.className='form-label';label.textContent=definition.label;
        const id=container.id+'-'+index;label.htmlFor=id;
        if(!schema.enum && !['string','number','integer','boolean'].includes(type)) {
          const note=document.createElement('p');note.className='small text-muted';note.textContent=definition.label+' · '+tr.advanced_parameters;wrapper.append(note);container.append(wrapper);return;
        }
        const enable=document.createElement('input');enable.type='checkbox';enable.className='form-check-input me-2';enable.id=id+'-include';
        const useLabel=document.createElement('label');useLabel.className='form-check-label mb-2';useLabel.htmlFor=enable.id;useLabel.textContent=tr.supply_parameter;
        const must=definition.required&&!Object.hasOwn(definition,'default');enable.checked=must||Object.hasOwn(values,definition.key);enable.disabled=must;
        let input;const choices=schema.enum||(type==='boolean'?[true,false]:null);
        if(choices){input=document.createElement('select');input.className='form-select';const blank=document.createElement('option');blank.value='';blank.textContent=tr.choose;input.append(blank);choices.forEach(value=>{const option=document.createElement('option');option.value=JSON.stringify(value);option.textContent=value===true?tr.yes:value===false?tr.no:value===null?tr.null_value:typeof value==='object'?JSON.stringify(value):String(value);input.append(option);});}
        else {input=document.createElement('input');input.className='form-control';input.type=['number','integer'].includes(type)?'number':schema.format==='date'?'date':'text';if(input.type==='number'){input.step=type==='integer'?'1':'any';if(schema.minimum!==undefined)input.min=schema.minimum;if(schema.maximum!==undefined)input.max=schema.maximum;}if(schema.maxLength!==undefined)input.maxLength=schema.maxLength;}
        input.id=id;input.disabled=!enable.checked;if(choices||input.type==='number')input.required=true;
        const current=Object.hasOwn(values,definition.key)?values[definition.key]:definition.default;
        if(current!==undefined)input.value=choices?JSON.stringify(current):current===null?'':String(current);
        if(current===null&&!choices){input.disabled=true;const hint=document.createElement('div');hint.className='form-text';hint.textContent=tr.null_value+' · '+tr.advanced_parameters;wrapper.append(hint);}
        function update(){
          if(!enable.checked)delete values[definition.key];
          else {try {if(choices){if(input.value==='')throw Error();values[definition.key]=JSON.parse(input.value);}else if(['number','integer'].includes(type)){if(input.value===''||!Number.isFinite(Number(input.value))||(type==='integer'&&!Number.isInteger(Number(input.value))))throw Error();values[definition.key]=Number(input.value);}else values[definition.key]=input.value;input.setCustomValidity('');}catch(_){input.setCustomValidity(tr.error);return;}}
          input.setCustomValidity('');source.value=JSON.stringify(values,null,2);changed();
        }
        enable.onchange=()=>{input.disabled=!enable.checked;update();};input.oninput=update;
        wrapper.append(label,document.createElement('br'),enable,useLabel,input);
        if(Object.hasOwn(definition,'default')){const hint=document.createElement('div');hint.className='form-text';hint.textContent=tr.parameter_default+' '+JSON.stringify(definition.default);wrapper.append(hint);}
        container.append(wrapper);
      });
    }
    const refresh=()=>{draw();changed();};listeners.set(source,refresh);source.addEventListener('input',refresh);draw();
  }
  window.TesseractReportsParameters={mount};
})();
