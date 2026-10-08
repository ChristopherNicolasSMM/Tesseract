// Percurso real da IDE e consumidores; servidor/banco descartáveis.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
  const base = process.env.REPORTS_TEST_URL || 'http://127.0.0.1:5068';
  const errors=[]; page.on('pageerror',error=>{errors.push(error.message);console.error('Page error:',error.message);});
  const login=await page.request.post(base+'/api/auth/login',{data:{username:'reports_test',password:'test-only-password'}});
  assert.equal(login.status(),200);
  const fixtures=await (await page.request.get(base+'/__reports_fixture')).json();
  await page.goto(base+'/reports/');
  async function state(value) { try { await page.waitForFunction(value=>document.querySelector('#report-status').dataset.state===value,value); } catch(error) { console.error('Expected state', value, await page.locator('#report-status').textContent(), await page.locator('#report-status').getAttribute('data-state')); throw error; } }
  async function confirm() { await page.waitForFunction(()=>{const modal=bootstrap.Modal.getInstance(document.getElementById('core-confirm-modal'));return modal?._isShown && !modal._isTransitioning;});await page.locator('#core-confirm-modal-ok').click();await page.locator('#core-confirm-modal').waitFor({state:'hidden'}); }
  async function create(key,name) {
    await page.locator('#report-key').fill(key);await page.locator('#report-name').fill(name);
    await page.locator('#create-template').click();await state('saved');
    await page.waitForFunction(()=>!document.querySelector('#add-text').disabled);
  }
  async function example(name) {
    await page.locator('#report-example').selectOption(name);await page.locator('#load-example').click();
    await confirm();await state('dirty');await page.locator('#save-report').click();await state('saved');
  }
  async function publish() {
    await page.locator('#publish-report').click();await confirm();await state('published');
    assert.equal(await page.locator('#save-report').isDisabled(),true);
    assert.equal(await page.locator('#load-example').isDisabled(),true);
  }
  await create('browser.example','Relatório navegador');
  await page.locator('#add-text').click();await page.locator('#node-text').fill('Texto confirmado');
  await page.locator('#save-report').click();await state('saved');await page.reload();
  await page.getByText('Texto confirmado',{exact:true}).first().waitFor();
  await page.locator('#report-tree button').last().click();
  await page.locator('#move-up').click();assert.equal(await page.locator('#report-paper button').first().textContent(),'Texto confirmado');
  await page.locator('#delete-node').click();assert.equal(await page.locator('#report-paper button').count(),1);
  await example('estoque-saldos');
  await page.locator('#report-tree button').last().click();
  await page.locator('#column-label-0').fill('Material alterado');
  await page.locator('#column-binding-0').selectOption(JSON.stringify({source:'item',path:['sku']}));
  assert.equal(await page.locator('#report-paper th').first().textContent(),'Material alterado');
  await page.locator('#save-report').click();await state('saved');
  assert.equal((await page.request.post(base+'/api/auth/update-theme',{data:{theme:'dark'}})).status(),200);
  await page.reload();await state('saved');await page.locator('#report-tree button').last().click();
  assert.equal(await page.locator('.reports-paper').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(39, 53, 73)');
  assert.equal(await page.locator('.reports-paper').evaluate(el=>getComputedStyle(el).color),'rgb(232, 238, 247)');
  if(process.env.REPORTS_SCREENSHOTS){fs.mkdirSync(process.env.REPORTS_SCREENSHOTS,{recursive:true});await page.screenshot({path:process.env.REPORTS_SCREENSHOTS+'/reports-dark.png',fullPage:true});}
  await page.locator('#add-page_break').click();
  await page.locator('#add-text').click();await page.locator('#node-text').fill('Após quebra explícita');
  await page.locator('#preview-report').click();await state('preview');
  const darkPreview=page.frameLocator('#html-preview');
  assert.equal(await darkPreview.locator('main').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(39, 53, 73)');
  const html=await page.locator('#html-preview').getAttribute('srcdoc');
  const printed=await browser.newPage();await printed.setContent(html);
  await printed.evaluate(()=>document.documentElement.dataset.theme='dark');
  await printed.emulateMedia({media:'print'});
  assert.equal(await printed.locator('main').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(255, 255, 255)');
  const pdf=await printed.pdf({preferCSSPageSize:true,printBackground:true});
  assert.equal(pdf.subarray(0,5).toString(),'%PDF-');
  if(process.env.REPORTS_SCREENSHOTS){await page.screenshot({path:process.env.REPORTS_SCREENSHOTS+'/reports-preview-dark.png',fullPage:true});fs.writeFileSync(process.env.REPORTS_SCREENSHOTS+'/reports-browser-print.pdf',pdf);}
  await printed.close();
  await page.locator('#reports-preview .btn-close').click();await page.locator('#reports-preview').waitFor({state:'hidden'});
  await page.emulateMedia({media:'print'});
  assert.equal(await page.locator('.reports-paper').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(255, 255, 255)');
  await page.emulateMedia({media:'screen'});
  assert.equal((await page.request.post(base+'/api/auth/update-theme',{data:{theme:'light'}})).status(),200);
  await page.reload();await state('saved');await page.locator('#report-tree button').last().click();
  assert.equal(await page.locator('.reports-paper').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(255, 255, 255)');
  if(process.env.REPORTS_SCREENSHOTS)await page.screenshot({path:process.env.REPORTS_SCREENSHOTS+'/reports-light.png',fullPage:true});
  await page.locator('#preview-report').click();await state('preview');
  assert.ok(await page.locator('#html-preview').getAttribute('srcdoc'));
  const preview = page.frameLocator('#html-preview');
  assert.match(await preview.locator('main').textContent(), /MALTE-PILSEN/);
  assert.equal(await page.locator('#print-report').isEnabled(),true);
  await page.locator('#html-preview').evaluate(frame=>{ frame.contentWindow.print=()=>{frame.dataset.printCalled='true';}; });
  await page.locator('#print-report').click();
  assert.equal(await page.locator('#html-preview').getAttribute('data-print-called'),'true');
  await page.locator('#reports-preview .btn-close').click();await page.locator('#reports-preview').waitFor({state:'hidden'});
  await publish();await page.locator('#clone-report').click();await state('saved');
  assert.equal(await page.locator('#version-select').inputValue(),'2');
  assert.equal(await page.locator('#save-report').isEnabled(),true);
  // Outro editor grava primeiro; tentativa local deve exibir conflito sem perder rascunho.
  const url=new URL(page.url()), id=url.searchParams.get('template');
  const token=(await (await page.request.get(base+'/api/reports/session')).json()).csrf_token;
  const revision=(await (await page.request.get(base+`/api/reports/templates/${id}/versions/2`)).json()).item;
  const update=await page.request.put(base+`/api/reports/templates/${id}/versions/2`,{headers:{'X-Reports-CSRF':token},data:{lock_version:revision.lock_version,layout:revision.layout,data_schema:revision.data_schema,sample_data:revision.sample_data,parameters:revision.parameters}});
  assert.equal(update.status(),200);await page.locator('#report-tree button').first().click();
  await page.locator('#node-text').fill('Rascunho preservado');await page.locator('#save-report').click();await state('error');
  assert.equal(await page.locator('#node-text').inputValue(),'Rascunho preservado');
  page.once('dialog',dialog=>dialog.accept());await page.reload();await state('saved');
  await create('browser.session','Relatório de sessão');await example('brewstation-session');
  await page.locator('#report-tree button').first().click();
  await page.getByRole('combobox',{name:'Conteúdo',exact:true}).selectOption('field');
  await page.locator('#node-binding').selectOption(JSON.stringify({source:'data',path:['session','name']}));
  await page.locator('#save-report').click();await state('saved');await publish();
  // Responsividade: papel acessível sem estourar horizontalmente o documento.
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>getComputedStyle(document.getElementById('main')).marginLeft==='0px');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
  await page.setViewportSize({width:1440,height:1000});
  for(const [url,consumer] of [[fixtures.saldo_url,'stock'],[fixtures.session_url,'session']]) {
    await page.goto(base+url);await page.locator(`[data-report-consumer="${consumer}"]`).click();
    await page.waitForFunction(()=>!document.querySelector('#reports-consumer-submit').disabled);
    await page.locator('#reports-consumer-submit').click();
    await page.waitForFunction(()=>!document.querySelector('#reports-consumer-print').disabled);
    assert.ok((await page.frameLocator('#reports-consumer-preview').locator('main').textContent()).trim());
    await page.locator('#reports-consumer-preview').evaluate(frame=>{frame.contentWindow.print=()=>{frame.dataset.printCalled='true';};});
    await page.locator('#reports-consumer-print').click();
    assert.equal(await page.locator('#reports-consumer-preview').getAttribute('data-print-called'),'true');
    await page.locator('#reports-consumer-modal .btn-close').click();
  }
  assert.deepEqual(errors,[]);await browser.close();
  console.log('Reports IDE, themes, print, conflict and consumer HTML/print passed');
})().catch(error=>{console.error(error);process.exit(1)});
