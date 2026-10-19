/* Executa o script real: precisão de apresentação, escape e contexto de filtros. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const charts=[],inputs=[],listeners={};
const context={querySelector:()=>null};
const form={querySelector:()=>null,append:input=>inputs.push(input)};
const nodes={
 'finance-workspace':{querySelectorAll:()=>[context,form]},
 'finance-context-form':context,
 'fw-org':{addEventListener:(name,fn)=>listeners[name]=fn},
 'finance-dashboard-data':{textContent:JSON.stringify({currency:'BRL',daily:[{date:'2026-10-19',realized_balance:'999999999999999999.99',projected_balance:'12.3456'}],
  categories:[{name:'<img src=x onerror=alert(1)>',amount:'12.3456'}],centers:[],monthly:[]})},
 'finance-balance-chart':{},'finance-categories-chart':{},'finance-centers-chart':{},'finance-monthly-chart':{}
};
class Chart{constructor(element,options){charts.push(options);}render(){}updateOptions(){}}
vm.runInNewContext(fs.readFileSync('static/js/financeiro_workspace.js','utf8'),{
 document:{getElementById:id=>nodes[id],createElement:()=>({}),documentElement:{getAttribute:()=> 'dark'},body:{classList:{contains:()=>false}}},
 window:{ApexCharts:Chart},ApexCharts:Chart,
 FormData:class{entries(){return Object.entries({organization_code:'A',date_from:'2026-10-01',date_to:'2026-10-31',tab:'cash',view:'accounts'});}},
 MutationObserver:class{observe(){}},console
});
assert.equal(charts.length,4);
assert.equal(charts[0].theme.mode,'dark');
assert.equal(charts[0].tooltip.y.formatter(0,{seriesIndex:0,dataPointIndex:0}),'999.999.999.999.999.999,99 BRL');
assert.equal(charts[0].tooltip.y.formatter(0,{seriesIndex:1,dataPointIndex:0}),'12,3456 BRL');
assert.match(charts[1].xaxis.categories[0],/^&lt;img/);
assert.ok(!charts[1].xaxis.categories[0].includes('<'));
assert.equal(inputs.find(input=>input.name==='organization_code').value,'A');
assert.equal(inputs.find(input=>input.name==='date_to').value,'2026-10-31');
console.log('Workspace JS: contexto, tema, precisão e escape conferidos.');
