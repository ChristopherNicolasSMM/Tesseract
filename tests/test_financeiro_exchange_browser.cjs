/* Navegador real; requests são atendidos pelo test_client Flask em memória. */
const {spawn} = require('node:child_process');
const readline = require('node:readline');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async()=>{
  const fixture=spawn(process.env.TEST_PYTHON || 'python',[path.join(__dirname,'ui_financeiro_fixture.py')],{stdio:['pipe','pipe','pipe']});
  let logs='';fixture.stderr.on('data',chunk=>{logs=(logs+chunk.toString()).slice(-6000);});
  const pending=new Map();let sequence=0;
  let readyResolve;const ready=new Promise(resolve=>readyResolve=resolve);
  readline.createInterface({input:fixture.stdout}).on('line',line=>{
    const message=JSON.parse(line);
    if(message.ready)readyResolve();else {const waiter=pending.get(message.id);pending.delete(message.id);message.error?waiter.reject(new Error(message.error)):waiter.resolve(message);}
  });
  function request(command){return new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});fixture.stdin.write(JSON.stringify({...command,id})+'\n');});}
  let browser;
  try {
    let readyTimer;
    try { await Promise.race([ready,new Promise((_,reject)=>{readyTimer=setTimeout(()=>reject(new Error('Fixture timeout: '+logs)),30000);})]); }
    finally { clearTimeout(readyTimer); }
    browser=await chromium.launch({headless:true,executablePath:process.env.TEST_CHROMIUM || undefined,args:['--no-sandbox','--disable-dev-shm-usage']});
    const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('http://tesseract.test/**',async route=>{
      const r=route.request();const url=new URL(r.url());
      const reply=await request({path:url.pathname+url.search,method:r.method(),body:(r.postDataBuffer()||Buffer.alloc(0)).toString('base64'),headers:{'Content-Type':r.headers()['content-type']||''}});
      const headers={...reply.headers};delete headers['Content-Length'];delete headers['Set-Cookie'];
      await route.fulfill({status:reply.status,headers,body:Buffer.from(reply.body,'base64')});
    });
    const origin='http://tesseract.test';
    await page.goto(origin+'/financeiro/exchange-rates/');
    async function api(path, data) {
      const result = await page.evaluate(async ({path,data}) => {
        const r = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
        return {status:r.status,body:await r.json()};
      },{path,data});
      assert.equal(result.status,201); return result.body.item;
    }
    await api('/api/financeiro/currencies',{code:'BRL',name:'Real',decimal_places:2});
    await api('/api/financeiro/currencies',{code:'USD',name:'Dólar',decimal_places:2});
    await api('/api/financeiro/policies',{organization_code:'UI_ORG',currency_code:'BRL',rounding:'HALF_UP'});
    await page.reload();
    await page.locator('#org').selectOption('UI_ORG');
    await page.locator('#source_currency').selectOption('USD');
    await page.locator('#target_currency').selectOption('BRL');
    await page.locator('#rate').fill('0');
    await page.locator('#valid_on').fill('2026-10-08');
    await page.locator('#rate_type').selectOption('MANUAL');
    await page.locator('#source').fill('Contrato demonstrativo');
    await page.getByRole('button',{name:'Cadastrar taxa',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'positiva'}).waitFor();
    assert.equal(await page.locator('#source').inputValue(),'Contrato demonstrativo');
    await page.locator('#rate').fill('5.25');
    await page.getByRole('button',{name:'Cadastrar taxa',exact:true}).click();
    await page.getByRole('cell',{name:'1 USD = 5.25 BRL',exact:true}).waitFor();
    assert.equal(await page.locator('#sidebar-nav a[href="/financeiro/exchange-rates/"]').count(),1);
    assert.equal(await page.locator('#sidebar-nav a[href="/financeiro/conversions/"]').count(),1);
    await page.goto(origin+'/financeiro/conversions/');
    await page.locator('#org').selectOption('UI_ORG');
    await page.locator('#source_currency').selectOption('USD');
    await page.locator('#amount').fill('10.01');
    await page.locator('#operation_date').fill('2026-10-08');
    await page.locator('#rate_id').selectOption('1');
    await page.locator('#reference').fill('Compra demonstrativa');
    const key=await page.locator('#idempotency_key').inputValue();
    await page.getByRole('button',{name:'Simular',exact:true}).click();
    await page.getByRole('status').filter({hasText:'52.55 BRL'}).waitFor();
    assert.equal(await page.locator('#idempotency_key').inputValue(),key);
    assert.equal(await page.getByRole('cell',{name:'Nenhum registro cadastrado.',exact:true}).count(),1);
    await page.getByRole('button',{name:'Confirmar no histórico',exact:true}).click();
    await page.getByRole('cell',{name:'Compra demonstrativa',exact:true}).waitFor();
    await page.getByText('Detalhes do cálculo',{exact:true}).click();
    assert.match(await page.locator('details').innerText(),/52.5525/);
    await page.goto(origin+'/financeiro/policy-versions/');
    assert.equal(await page.locator('#sidebar-nav a[href="/financeiro/policy-versions/"]').count(),1);
    await page.locator('#version-org').selectOption('UI_ORG');
    assert.equal(await page.locator('#expected_version').inputValue(),'1');
    await page.locator('#version-scale').fill('2');
    await page.locator('#version-rounding').selectOption('HALF_UP');
    await page.locator('#version-date').fill('2026-10-08');
    await page.locator('#version-reason').fill('Revisão demonstrativa');
    await page.getByRole('button',{name:'Cadastrar versão',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'deve alterar'}).waitFor();
    assert.equal(await page.locator('#version-reason').inputValue(),'Revisão demonstrativa');
    assert.equal(await page.locator('#expected_version').inputValue(),'1');
    await page.locator('#version-rounding').selectOption('HALF_EVEN');
    await page.getByRole('button',{name:'Cadastrar versão',exact:true}).click();
    await page.getByRole('cell',{name:'2 / #1',exact:true}).waitFor();
    await page.goto(origin+'/financeiro/conversions/');
    await page.locator('#org').selectOption('UI_ORG');
    await page.locator('#source_currency').selectOption('BRL');
    await page.locator('#amount').fill('1.005');
    await page.locator('#operation_date').fill('2026-10-08');
    await page.locator('#reference').fill('Conversão versão 2');
    await page.getByRole('button',{name:'Simular',exact:true}).click();
    await page.getByRole('status').filter({hasText:'1.01 BRL'}).waitFor();
    await page.locator('#policy_version_id').selectOption('1');
    await page.locator('#operation_date').fill('2026-10-07');
    await page.getByRole('button',{name:'Simular',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'ainda não válida'}).waitFor();
    assert.equal(await page.locator('#policy_version_id').inputValue(),'1');
    assert.equal(await page.locator('#reference').inputValue(),'Conversão versão 2');
    await page.locator('#operation_date').fill('2026-10-08');
    await page.getByRole('button',{name:'Simular',exact:true}).click();
    await page.getByRole('status').filter({hasText:'1.00 BRL'}).waitFor();
    await page.getByRole('button',{name:'Confirmar no histórico',exact:true}).click();
    const revisedRow=page.locator('tr').filter({has:page.getByRole('cell',{name:'Conversão versão 2',exact:true})});
    await revisedRow.waitFor();
    await revisedRow.getByText('Detalhes do cálculo',{exact:true}).click();
    assert.match(await revisedRow.innerText(),/versão 2 \(#1\)/);
    assert.match(await revisedRow.innerText(),/Revisão demonstrativa/);
    const oldRow=page.locator('tr').filter({has:page.getByRole('cell',{name:'Compra demonstrativa',exact:true})});
    assert.match(await oldRow.innerText(),/52.55 BRL/);
    await oldRow.getByText('Detalhes do cálculo',{exact:true}).click();
    assert.match(await oldRow.innerText(),/versão 1/);
    for(const theme of ['dark','light']) {
      await page.evaluate(async theme=>fetch('/api/auth/update-theme',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({theme})}),theme);
      await page.reload();
      assert.equal(await page.locator('html').getAttribute('data-theme'),theme);
      await page.evaluate(()=>window.scrollTo(0,0));
      if(process.env.UI_SCREENSHOT_DIR) await page.screenshot({path:path.join(process.env.UI_SCREENSHOT_DIR,'cambio-'+theme+'.png'),fullPage:true});
      await page.goto(origin+'/financeiro/policy-versions/');
      if(process.env.UI_SCREENSHOT_DIR) await page.screenshot({path:path.join(process.env.UI_SCREENSHOT_DIR,'versoes-'+theme+'.png'),fullPage:true});
      await page.goto(origin+'/financeiro/conversions/');
    }
    assert.deepEqual(errors,[]);
    console.log('Câmbio: formulário preservado, taxa, simulação sem gravação, confirmação, snapshot, versões explícitas, data, menu e temas aprovados.');
  } finally {if(browser)await browser.close();fixture.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
