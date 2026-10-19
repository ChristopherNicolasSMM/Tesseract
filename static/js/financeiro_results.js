/* Séries visuais aproximadas; tabelas e tooltips preservam valores decimais exatos. */
(() => {
 'use strict';
 const element=document.getElementById('results-dashboard-data');if(!element||!window.ApexCharts)return;
 const data=JSON.parse(element.textContent),charts=[];
 const escape=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const money=v=>{const parts=String(v).split('.');return parts[0].replace(/\B(?=(\d{3})+(?!\d))/g,'.')+','+(parts[1]||'').padEnd(2,'0')+' '+data.currency;};
 const dark=()=>document.documentElement.getAttribute('data-theme')==='dark';
 function draw(id,series,labels,type){
  const target=document.getElementById(id);if(!target)return;
  const chart=new ApexCharts(target,{chart:{type,height:300,animations:{enabled:false},toolbar:{show:false}},
   series:series.map(s=>({...s,data:s.data.map(Number)})),theme:{mode:dark()?'dark':'light'},
   colors:['#0d6efd','#20a080'],xaxis:{categories:labels.map(escape)},stroke:{width:2},dataLabels:{enabled:false},
   tooltip:{y:{formatter:(v,{seriesIndex,dataPointIndex})=>money(series[seriesIndex].data[dataPointIndex])}},
   noData:{text:'Sem valores reconhecidos neste período'}});chart.render();charts.push(chart);
 }
 draw('results-monthly-chart',[{name:'Receita líquida',data:data.monthly.map(r=>r.net_revenue)},{name:'Resultado líquido',data:data.monthly.map(r=>r.net_result)}],data.monthly.map(r=>r.period),'line');
 draw('results-formation-chart',[{name:'Formação do resultado',data:data.formation.map(r=>r.amount)}],data.formation.map(r=>r.label),'bar');
 for(const field of ['categories','centers'])draw('results-'+field+'-chart',[{name:'Gastos líquidos',data:data[field].map(r=>r.amount)}],data[field].map(r=>r.name),'bar');
 new MutationObserver(()=>charts.forEach(c=>c.updateOptions({theme:{mode:dark()?'dark':'light'}}))).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme','class']});
})();
