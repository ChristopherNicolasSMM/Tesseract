const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const configs=[],updates=[];
const data={currency:'BRL',monthly:[{period:'2026-10',net_revenue:'9007199254740993.01',net_result:'0.01'}],formation:[{label:'<img src=x>',amount:'0.01'}],categories:[],centers:[]};
let dark=false,observer;
const document={getElementById:id=>id==='results-dashboard-data'?{textContent:JSON.stringify(data)}:{},documentElement:{getAttribute:()=>dark?'dark':'light'}};
class ApexCharts{constructor(target,config){configs.push(config)}render(){}updateOptions(value){updates.push(value)}}
class MutationObserver{constructor(callback){observer=callback}observe(){}}
vm.runInNewContext(fs.readFileSync('static/js/financeiro_results.js','utf8'),{document,window:{ApexCharts},ApexCharts,MutationObserver});
assert.equal(configs.length,4);
assert.equal(configs[0].tooltip.y.formatter(0,{seriesIndex:0,dataPointIndex:0}),'9.007.199.254.740.993,01 BRL');
assert.equal(configs[1].xaxis.categories[0],'&lt;img src=x&gt;');
dark=true;observer();assert.equal(updates.length,4);assert.equal(updates[0].theme.mode,'dark');
console.log('Financeiro resultados: precisão textual, escape e tema verificados.');
