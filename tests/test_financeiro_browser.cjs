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
    await page.goto(origin+'/admin/organizations/');
    assert.equal(await page.locator('script[src*="/plugins/getcep/static/getcep.js?v=1.0.1"]').count(),1);
    if(process.env.BASELINE_PROBE){
      const field=page.locator('input[name=cep]').first();await field.evaluate(el=>{el.value='01001000';el.dispatchEvent(new Event('blur'));});
      await page.waitForTimeout(300);console.log('CEP result:',await page.locator('input[name=cidade]').first().inputValue());console.log('Page errors:',errors);return;
    }
    await page.getByRole('button',{name:'Nova organização'}).click();
    await page.locator('[name=code]').fill('NEW_ORG');await page.locator('[name=name]').fill('Nome digitado');
    await page.locator('[name=legal_name]').fill('Razão digitada');await page.locator('[name=cep]').fill('01001000');
    await page.getByRole('button',{name:'Consultar CEP'}).click();
    await page.waitForFunction(()=>document.querySelector('[name=cidade]').value==='São Paulo');
    assert.match(await page.locator('[role=status]').innerText(),/ViaCEP/);
    await page.locator('[name=email]').fill('inválido');
    await page.getByRole('button',{name:'Criar organização',exact:true}).click();
    await page.getByRole('alert').waitFor();
    assert.equal(await page.locator('[name=legal_name]').inputValue(),'Razão digitada');
    assert.equal(await page.locator('[name=cidade]').inputValue(),'São Paulo');
    assert.match(await page.getByRole('alert').innerText(),/E-mail/);
    await page.locator('[name=email]').fill('valid@test.local');await page.getByRole('button',{name:'Criar organização',exact:true}).click();
    await page.getByRole('heading',{name:'Organização: Nome digitado',exact:true}).waitFor();
    assert.equal(await page.locator('[name=legal_name]').inputValue(),'Razão digitada');
    assert.equal(await page.locator('[name=email]').first().inputValue(),'valid@test.local');
    // API errors visible, all existing address fields retained.
    await page.locator('[name=cep]').fill('99999999');await page.getByRole('button',{name:'Consultar CEP'}).click();
    await page.waitForFunction(()=>document.querySelector('[role=status]').textContent.includes('não encontrado'));
    assert.equal(await page.locator('[name=cidade]').inputValue(),'São Paulo');
    assert.match(await page.locator('[role=status]').innerText(),/não encontrado/);
    await page.locator('[name=cep]').fill('88888888');await page.getByRole('button',{name:'Consultar CEP'}).click();
    await page.waitForFunction(()=>document.querySelector('[role=status]').textContent.includes('indisponível'));
    assert.match(await page.locator('[role=status]').innerText(),/manual/);
    assert.equal(await page.locator('[name=cidade]').inputValue(),'São Paulo');
    // Existing generated Estoque form: actual field names and plugin asset integration.
    await page.goto(origin+'/estoque/enderecos/');
    await page.locator('button[data-bs-target="#novoRegistroForm"]').click();
    await page.locator('[name=cep]').fill('01001000');
    await page.getByRole('button',{name:'Consultar CEP'}).click();
    await page.waitForFunction(()=>document.querySelector('[name=cidade]').value==='São Paulo');
    assert.equal(await page.locator('[name=estado]').inputValue(),'SP');
    await page.goto(origin+'/financeiro/currencies/');
    assert.equal(await page.locator('#sidebar-nav a[href="/financeiro/currencies/"]').count(),1);
    assert.equal(await page.locator('#sidebar-nav a[href="/financeiro/monetary-policies/"]').count(),1);
    // Use the real stored preference and dark stylesheet, not a synthetic attribute.
    for(const theme of ['dark','light']) {
      const result=await page.evaluate(async theme=>{
        const response=await fetch('/api/auth/update-theme',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({theme})});
        return response.json();
      },theme);
      assert.equal(result.success,true);
      await page.reload();
      assert.equal(await page.locator('html').getAttribute('data-theme'),theme);
      assert.equal(await page.locator('#theme-dark-css').count(),theme==='dark'?1:0);
      assert.equal(await page.locator('.pagetitle h1').innerText(),'Moedas');
      assert.equal(await page.locator('table.table-striped').count(),1);
      await page.goto(origin+'/admin/organizations/');
      assert.equal(await page.locator('html').getAttribute('data-theme'),theme);
      assert.equal(await page.locator('table.table-striped').count(),1);
      if(process.env.UI_SCREENSHOT_DIR) await page.screenshot({path:path.join(process.env.UI_SCREENSHOT_DIR,'organizacoes-'+theme+'.png')});
      await page.goto(origin+'/financeiro/currencies/');
      if(process.env.UI_SCREENSHOT_DIR) await page.screenshot({path:path.join(process.env.UI_SCREENSHOT_DIR,'financeiro-'+theme+'.png')});
    }
    assert.deepEqual(errors,[]);
    console.log('Navegador: CEP, erro visível, formulário preservado, persistência, menu automático e temas aprovados.');
  } finally {if(browser)await browser.close();fixture.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
