/* O servidor mantém os valores monetários exatos; gráficos são apresentação. */
(() => {
  'use strict';
  const root=document.getElementById('finance-workspace');
  if(!root)return;
  const contextForm=document.getElementById('finance-context-form');
  const organization=document.getElementById('fw-org');
  organization?.addEventListener('change',()=>{
    const account=document.getElementById('fw-account');
    if(account){account.value='';account.disabled=true;}
    // Trocar organização deixa o detalhe, cujo documento pertence à organização anterior.
    const title=contextForm?.querySelector('[name="title_id"]');
    if(title){title.remove();contextForm.querySelector('[name="view"]').value='list';}
  });
  // Um único contexto em todos os filtros GET, inclusive cadastros legados.
  const shared=Object.fromEntries(new FormData(contextForm).entries());
  root.querySelectorAll('form[method="get"]').forEach(form=>{
    if(form===contextForm)return;
    for(const [key,value] of Object.entries(shared)){
      if(!['organization_code','date_from','date_to','account_id','tab','view'].includes(key))continue;
      if(!form.querySelector(`[name="${key}"]`)){
        const input=document.createElement('input');input.type='hidden';input.name=key;input.value=value;form.append(input);
      }
    }
  });
  const payload=document.getElementById('finance-dashboard-data');
  if(!payload||!window.ApexCharts)return;
  const data=JSON.parse(payload.textContent),charts=[];
  const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money=value=>{const parts=String(value).split('.');return parts[0].replace(/\B(?=(\d{3})+(?!\d))/g,'.')+','+(parts[1]||'').padEnd(2,'0')+' '+data.currency;};
  const dark=()=>document.documentElement.getAttribute('data-theme')==='dark'||document.body.classList.contains('theme-dark');
  function draw(id,series,labels,type='line'){
    const element=document.getElementById(id);if(!element)return;
    const options={chart:{type,height:280,toolbar:{show:false},animations:{enabled:false}},series:series.map(s=>({...s,data:s.data.map(Number)})),
      theme:{mode:dark()?'dark':'light'},colors:['#0d6efd','#20a080'],
      xaxis:{categories:labels.map(escape)},yaxis:{labels:{formatter:v=>Number(v).toLocaleString('pt-BR',{maximumFractionDigits:2})}},
      tooltip:{y:{formatter:(value,{seriesIndex,dataPointIndex})=>money(series[seriesIndex].data[dataPointIndex])}},noData:{text:'Sem movimentos no período'},dataLabels:{enabled:false},
      stroke:{width:2},legend:{position:'top'}};
    const chart=new ApexCharts(element,options);chart.render();charts.push(chart);
  }
  draw('finance-balance-chart',[{name:'Realizado',data:data.daily.map(r=>r.realized_balance)},{name:'Projetado',data:data.daily.map(r=>r.projected_balance)}],data.daily.map(r=>r.date));
  for(const field of ['categories','centers'])draw('finance-'+field+'-chart',[{name:'Pagamentos líquidos',data:data[field].map(r=>r.amount)}],data[field].map(r=>r.name),'bar');
  draw('finance-monthly-chart',[{name:'Entradas',data:data.monthly.map(r=>r.income)},{name:'Saídas',data:data.monthly.map(r=>r.outflow)}],data.monthly.map(r=>r.month),'bar');
  new MutationObserver(()=>charts.forEach(c=>c.updateOptions({theme:{mode:dark()?'dark':'light'}}))).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme','class']});
})();
