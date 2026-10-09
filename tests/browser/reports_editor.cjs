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
    assert.equal(await page.locator('#add-section').isDisabled(),true);
    assert.equal(await page.locator('#add-columns').isDisabled(),true);
    assert.equal(await page.locator('#add-image').isDisabled(),true);
    assert.equal(await page.locator('#page-format').isDisabled(),true);
    assert.equal(await page.locator('#page-number-pages').isDisabled(),true);
    assert.equal(await page.locator('#duplicate-node').isDisabled(),true);
    assert.equal(await page.locator('#undo-report').isDisabled(),true);
    assert.equal(await page.locator('#redo-report').isDisabled(),true);
  }
  await create('browser.example','Relatório navegador');
  assert.equal(await page.locator('#undo-report').isDisabled(),true);
  await page.locator('#add-text').click();await page.locator('#node-text').fill('Alteração reversível');
  await page.locator('#undo-report').click();assert.equal(await page.locator('#node-text').inputValue(),'Texto');
  await page.locator('#undo-report').click();assert.equal(await page.locator('#report-tree button').count(),1);
  await page.locator('#redo-report').click();await page.locator('#redo-report').click();
  assert.equal(await page.locator('#node-text').inputValue(),'Alteração reversível');
  await page.locator('#undo-report').click();await page.locator('#node-text').fill('Outra alteração');
  assert.equal(await page.locator('#redo-report').isDisabled(),true);
  await page.locator('#undo-report').click();await page.locator('#undo-report').click();
  await page.locator('#tab-data').click();const originalSample=await page.locator('#sample-data').inputValue();
  await page.locator('#sample-data').fill('{');await page.locator('#undo-report').click();
  assert.equal(await page.locator('#sample-data').inputValue(),originalSample);
  await page.keyboard.press('Control+s');await state('saved');
  assert.equal(await page.locator('#undo-report').isDisabled(),true);assert.equal(await page.locator('#redo-report').isDisabled(),true);
  await page.locator('#tab-layout').click();await page.locator('#add-divider').click();
  await page.locator('#tab-layout').focus();await page.keyboard.press('Control+z');
  assert.equal(await page.locator('#report-tree button').count(),1);
  await page.keyboard.press('Control+Shift+z');assert.equal(await page.locator('#report-tree button').count(),2);
  await page.locator('#undo-report').click();

  await page.locator('#report-page-settings > summary').click();
  await page.locator('#page-format').selectOption('A5');await page.locator('#page-orientation').selectOption('landscape');
  await page.locator('#page-margin-left').fill('41');await page.locator('#save-report').click();await state('error');
  await page.locator('#page-margin-left').fill('20');await page.locator('#page-number-pages').check();
  await page.locator('#save-report').click();await state('saved');await page.reload();await state('saved');
  assert.equal(await page.locator('#page-format').inputValue(),'A5');assert.equal(await page.locator('#page-orientation').inputValue(),'landscape');
  assert.equal(await page.locator('#page-margin-left').inputValue(),'20');assert.equal(await page.locator('#page-number-pages').isChecked(),true);
  await page.locator('#report-page-settings > summary').click();await page.locator('#reset-page').click();
  await page.locator('#add-text').click();await page.locator('#node-text').fill('Texto confirmado');
  await page.locator('#style-font_size').fill('7');
  await page.locator('#save-report').click();await state('error');
  assert.equal(await page.locator('#style-font_size').inputValue(),'7');
  await page.locator('#style-font_size').fill('24');
  await page.locator('#style-align').selectOption('right');
  await page.locator('#style-bold').selectOption('true');
  await page.locator('#save-report').click();await state('saved');await page.reload();await state('saved');
  await page.getByText('Texto confirmado',{exact:true}).first().waitFor();
  assert.equal(await page.locator('#report-paper button').last().evaluate(el=>getComputedStyle(el).fontSize),'32px');
  assert.equal(await page.locator('#report-paper button').last().evaluate(el=>getComputedStyle(el).textAlign),'right');
  await page.locator('#report-tree button').last().click();
  await page.locator('#move-up').click();assert.equal(await page.locator('#report-paper button').first().textContent(),'Texto confirmado');
  await page.locator('#delete-node').click();assert.equal(await page.locator('#report-paper button').count(),1);
  await page.locator('#add-section').click();
  await page.locator('#add-text').click();await page.locator('#node-text').fill('Texto na seção');
  await page.locator('#duplicate-node').click();await page.locator('#node-text').fill('Texto duplicado');
  assert.equal(await page.locator('.report-section-children button').count(),2);
  await page.locator('#move-up').click();assert.equal(await page.locator('.report-section-children button').first().textContent(),'Texto duplicado');
  await page.locator('#node-parent').selectOption('');assert.equal(await page.locator('.report-section-children button').count(),1);
  await page.locator('#report-tree button').filter({hasText:/^Seção$/}).first().click();
  await page.locator('#duplicate-node').click();assert.equal(await page.locator('.report-section').count(),2);
  await page.locator('#save-report').click();await state('saved');await page.reload();await state('saved');
  assert.equal(await page.locator('.report-section').count(),2);
  assert.equal(await page.locator('.report-section-children button').count(),2);
  await page.locator('#report-tree button').filter({hasText:/^Seção$/}).last().click();await page.locator('#delete-node').click();
  assert.equal(await page.locator('.report-section').count(),1);
  await page.locator('#report-tree button').filter({hasText:/^Seção$/}).first().click();
  await page.locator('#block-key').fill('browser.header');await page.locator('#block-name').fill('Cabeçalho reutilizável');
  await page.locator('#save-block').click();await page.waitForFunction(()=>document.querySelector('#block-select').selectedOptions[0]?.textContent==='Cabeçalho reutilizável'&&!document.querySelector('#insert-block').disabled);
  const savedBlockId=await page.locator('#block-select').inputValue();
  await page.locator('#report-tree button').filter({hasText:'Texto na seção'}).first().click();await page.locator('#node-text').fill('Fonte alterada');
  await page.locator('#insert-block').click();await state('dirty');
  await page.waitForFunction(()=>document.querySelectorAll('.report-section').length===2);
  assert.equal(await page.locator('#report-paper').getByText('Texto na seção',{exact:true}).count(),1);
  await page.locator('#save-report').click();await state('saved');await page.reload();await state('saved');
  assert.equal(await page.locator('.report-section').count(),2);
  await page.locator('#block-select').selectOption(savedBlockId);await page.locator('#archive-block').click();await confirm();
  await page.waitForFunction(id=>!Array.from(document.querySelector('#block-select').options).some(option=>option.value===id),savedBlockId);
  assert.equal(await page.locator('.report-section').count(),2);
  await page.locator('#report-tree button').filter({hasText:/^Seção$/}).last().click();await page.locator('#delete-node').click();
  await page.locator('#report-tree button').filter({hasText:'Fonte alterada'}).click();await page.locator('#node-text').fill('Texto na seção');
  await page.locator('#add-columns').click();
  await page.locator('#section-columns').selectOption('3');await page.locator('#section-gap').fill('12');
  await page.locator('#report-tree button').filter({hasText:/^Seção$/}).last().click();await page.locator('#add-text').click();await page.locator('#node-text').fill('Coluna B');
  await page.locator('#report-tree button').filter({hasText:/^Seção$/}).nth(2).click();await page.locator('#add-text').click();await page.locator('#node-text').fill('Coluna A');
  const logoFile={name:'logo.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABAAAAAICAIAAAB/FOjAAAAAFklEQVR4nGM0TpvJQApgIkn1qAYiAQDfnQFC17euhQAAAABJRU5ErkJggg==','base64')};
  const logoChooser=page.waitForEvent('filechooser');await page.locator('#add-image').click();await (await logoChooser).setFiles(logoFile);
  await page.locator('#image-width').waitFor();assert.equal(await page.locator('#pagination-break_before').isDisabled(),true);assert.equal(await page.locator('#add-page_break').isDisabled(),true);await page.locator('#image-width').fill('4');await page.locator('#save-report').click();await state('error');
  await page.locator('#image-width').fill('56');await page.locator('#image-height').fill('20');await page.locator('#image-alt').fill('Logotipo de teste');await page.locator('#style-align').selectOption('center');
  await page.locator('#image-replace-file').setInputFiles({name:'invalid.png',mimeType:'image/png',buffer:Buffer.from('<svg/>')});await state('error');
  assert.equal(await page.locator('#report-paper img').count(),1);
  await page.locator('#image-replace-file').setInputFiles({name:'logo.jpg',mimeType:'image/jpeg',buffer:Buffer.from('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAIABADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwBtFFFfNHAf/9k=','base64')});await state('dirty');
  assert.equal(await page.locator('.report-section-children').filter({has:page.locator('.report-section')}).last().evaluate(el=>getComputedStyle(el).display),'grid');
  await page.locator('#save-report').click();await state('saved');await page.reload();await state('saved');
  assert.equal(await page.locator('.report-section-children[style*="grid"]').count(),1);
  await page.locator('#report-tree button').filter({hasText:'Imagem / logotipo'}).click();
  assert.equal(await page.locator('#image-width').inputValue(),'56');assert.equal(await page.locator('#image-height').inputValue(),'20');
  assert.equal(await page.locator('#image-alt').inputValue(),'Logotipo de teste');
  if(process.env.REPORTS_SCREENSHOTS){fs.mkdirSync(process.env.REPORTS_SCREENSHOTS,{recursive:true});await page.locator('#pane-layout').screenshot({path:process.env.REPORTS_SCREENSHOTS+'/reports-images.png'});}
  assert.ok((await page.locator('#report-paper img').getAttribute('src')).startsWith('data:image/jpeg;base64,'));
  await page.locator('#duplicate-node').click();assert.equal(await page.locator('#report-paper img').count(),2);
  assert.equal(await page.locator('#image-width').inputValue(),'56');
  await page.locator('#delete-node').click();assert.equal(await page.locator('#report-paper img').count(),1);
  await page.locator('#save-report').click();await state('saved');
  const compositionUrl=new URL(page.url()),compositionCsrf=await page.locator('#reports-workspace').getAttribute('data-csrf');
  const composition=await page.request.post(base+`/api/reports/templates/${compositionUrl.searchParams.get('template')}/versions/1/preview`,{headers:{'X-Reports-CSRF':compositionCsrf},data:{format:'html',parameters:{}}});
  assert.equal(composition.status(),200);const compositionHtml=(await composition.json()).html;assert.ok(compositionHtml.includes('repeat(3,minmax(0,1fr));gap:12pt'));
  await page.evaluate(html=>{const frame=document.createElement('iframe');frame.id='composition-check';frame.style.width='900px';frame.srcdoc=html;document.body.append(frame);},compositionHtml);
  const composed=page.frameLocator('#composition-check').locator('.report-columns');await composed.waitFor();
  assert.equal(await composed.evaluate(el=>getComputedStyle(el).display),'grid');
  const logoPreview=page.frameLocator('#composition-check').locator('img');
  await page.waitForFunction(()=>document.querySelector('#composition-check').contentDocument.querySelector('img')?.naturalWidth===16);
  assert.equal(await logoPreview.getAttribute('alt'),'Logotipo de teste');
  await page.locator('#composition-check').evaluate(el=>el.contentDocument.documentElement.dataset.theme='dark');
  assert.equal(await page.frameLocator('#composition-check').locator('.report-document').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(39, 53, 73)');
  const cellPositions=await composed.evaluate(el=>Array.from(el.children).map(child=>child.getBoundingClientRect().x));assert.ok(cellPositions[1]>cellPositions[0]);
  await page.locator('#composition-check').evaluate(el=>el.style.width='350px');
  await page.waitForFunction(()=>getComputedStyle(document.querySelector('#composition-check').contentDocument.querySelector('.report-columns')).display==='block');
  await page.emulateMedia({media:'print'});assert.equal(await composed.evaluate(el=>getComputedStyle(el).display),'grid');
  assert.equal(await logoPreview.evaluate(el=>el.naturalWidth),16);
  assert.equal(await page.frameLocator('#composition-check').locator('.report-document').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(255, 255, 255)');
  assert.equal((await composed.evaluate(el=>getComputedStyle(el).gridTemplateColumns)).split(' ').length,3);
  await page.emulateMedia({media:'screen'});await page.locator('#composition-check').evaluate(el=>el.remove());

  await example('estoque-saldos');
  await page.locator('#report-tree button').last().click();
  await page.locator('#column-label-0').fill('Material alterado');
  await page.locator('#column-width-0').fill('30');
  await page.locator('#column-align-0').selectOption('right');
  await page.locator('#style-cell_padding').fill('8');
  await page.locator('#column-format-2-kind').selectOption('number');
  await page.locator('#column-format-2-decimals').fill('1');
  await page.locator('#column-format-3-kind').selectOption('currency');
  await page.locator('#column-aggregate-3').selectOption('sum');
  await page.locator('#column-binding-0').selectOption(JSON.stringify({source:'item',path:['sku']}));
  assert.equal(await page.locator('#report-paper th').first().textContent(),'Material alterado');
  await page.locator('#tab-parameters').click();
  await page.locator('#parameter-definitions').fill(JSON.stringify([
    {key:'title',label:'Título do relatório',schema:{type:'string'},required:true,default:'Padrão'},
    {key:'count',label:'Contagem',schema:{type:['integer','null'],minimum:0},default:0},
    {key:'flag',label:'Confirmado',schema:{type:'boolean'},default:false},
    {key:'options',label:'Opções avançadas',schema:{type:'object'},default:{}},
  ]));
  await page.locator('#parameter-values').focus();
  await page.locator('#parameter-form-1-include').check();
  await page.locator('#parameter-form-2-include').check();
  assert.deepEqual(JSON.parse(await page.locator('#parameter-values').inputValue()),{count:0,flag:false});
  await page.locator('#parameter-values').fill(JSON.stringify({count:null,flag:false}));
  assert.equal(await page.locator('#parameter-form-1').isDisabled(),true);
  assert.deepEqual(JSON.parse(await page.locator('#parameter-values').inputValue()),{count:null,flag:false});
  await page.locator('#parameter-values').fill(JSON.stringify({count:0,flag:false}));
  if(process.env.REPORTS_SCREENSHOTS)await page.screenshot({path:process.env.REPORTS_SCREENSHOTS+'/reports-parameters.png',fullPage:true});
  await page.locator('#parameter-form-0-include').check();await page.locator('#parameter-form-0').fill('Título informado');
  await page.locator('#save-report').click();await state('saved');
  await page.locator('#tab-layout').click();
  assert.equal((await page.request.post(base+'/api/auth/update-theme',{data:{theme:'dark'}})).status(),200);
  await page.reload();await state('saved');await page.locator('#report-tree button').last().click();
  assert.equal(await page.locator('.reports-paper').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(39, 53, 73)');
  assert.equal(await page.locator('.reports-paper').evaluate(el=>getComputedStyle(el).color),'rgb(232, 238, 247)');
  if(process.env.REPORTS_SCREENSHOTS){fs.mkdirSync(process.env.REPORTS_SCREENSHOTS,{recursive:true});await page.screenshot({path:process.env.REPORTS_SCREENSHOTS+'/reports-dark.png',fullPage:true});}
  assert.equal(await page.locator('#column-aggregate-3').inputValue(),'sum');
  await page.locator('#add-text').click();await page.locator('#node-text').fill('Conteúdo condicionado');
  await page.locator('#condition-enabled').selectOption('true');
  await page.locator('#condition-binding').selectOption(JSON.stringify({source:'parameters',path:['flag']}));
  await page.locator('#save-report').click();await state('saved');
  await page.reload();await state('saved');await page.locator('#report-tree button').last().click();
  assert.equal(await page.locator('#condition-enabled').inputValue(),'true');
  assert.equal(await page.locator('#condition-type').inputValue(),'boolean');
  const calculationUrl=new URL(page.url()),calculationCsrf=await page.locator('#reports-workspace').getAttribute('data-csrf');
  for(const flag of [false,true]) {
    const response=await page.request.post(base+`/api/reports/templates/${calculationUrl.searchParams.get('template')}/versions/1/preview`,{headers:{'X-Reports-CSRF':calculationCsrf},data:{format:'html',parameters:{flag}}});
    assert.equal(response.status(),200);const value=(await response.json()).html;
    assert.equal(value.includes('Conteúdo condicionado'),flag);assert.ok(value.includes('<tfoot>'));
  }
  await page.locator('#add-page_break').click();
  await page.locator('#add-text').click();await page.locator('#node-text').fill('Após quebra explícita');
  await page.locator('#preview-report').click();await state('preview');
  const darkPreview=page.frameLocator('#html-preview');
  assert.equal(await darkPreview.getByText('Conteúdo condicionado',{exact:true}).count(),0);
  assert.equal(await darkPreview.locator('tfoot').count(),1);
  assert.equal(await darkPreview.locator('main').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(39, 53, 73)');
  const html=await page.locator('#html-preview').getAttribute('srcdoc');
  const printed=await browser.newPage();await printed.setContent(html);
  await printed.evaluate(()=>document.documentElement.dataset.theme='dark');
  await printed.emulateMedia({media:'print'});
  assert.equal(await printed.locator('main').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(255, 255, 255)');
  const pdf=await printed.pdf({preferCSSPageSize:true,printBackground:true});
  assert.equal(pdf.subarray(0,5).toString(),'%PDF-');
  if(process.env.REPORTS_SCREENSHOTS){await page.waitForFunction(()=>!bootstrap.Modal.getInstance(document.getElementById('reports-preview'))._isTransitioning);await page.screenshot({path:process.env.REPORTS_SCREENSHOTS+'/reports-preview-dark.png',fullPage:true});fs.writeFileSync(process.env.REPORTS_SCREENSHOTS+'/reports-browser-print.pdf',pdf);}
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
  assert.match(await page.frameLocator('#html-preview').locator('main').textContent(),/R\$ 6,50/);
  const preview = page.frameLocator('#html-preview');
  assert.match(await preview.locator('main').textContent(), /MALTE-PILSEN/);
  assert.equal(await preview.locator('th').first().evaluate(el=>getComputedStyle(el).textAlign),'right');
  assert.ok(Math.abs(await preview.locator('td').first().evaluate(el=>parseFloat(getComputedStyle(el).paddingTop))-32/3)<0.02);
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
  for(const [url,consumer] of [[fixtures.saldo_url,'stock']]) {
    await page.goto(base+url);await page.locator(`[data-report-consumer="${consumer}"]`).click();
    await page.waitForFunction(()=>!document.querySelector('#reports-consumer-submit').disabled);
    if(consumer==='stock'){await page.locator('#reports-consumer-parameter-fields-1-include').check();await page.locator('#reports-consumer-parameter-fields-2-include').check();assert.deepEqual(JSON.parse(await page.locator('#reports-consumer-parameters').inputValue()),{count:0,flag:false});}
    await page.locator('#reports-consumer-submit').click();
    await page.waitForFunction(()=>!document.querySelector('#reports-consumer-print').disabled);
    assert.ok((await page.frameLocator('#reports-consumer-preview').locator('main').textContent()).trim());
    await page.locator('#reports-consumer-preview').evaluate(frame=>{frame.contentWindow.print=()=>{frame.dataset.printCalled='true';};});
    await page.locator('#reports-consumer-print').click();
    assert.equal(await page.locator('#reports-consumer-preview').getAttribute('data-print-called'),'true');
    await page.locator('#reports-consumer-modal .btn-close').click();
  }
  await page.goto(base+'/reports/');await create('browser.pagination','Paginação validada');
  const paginationQuery=new URL(page.url()),paginationId=paginationQuery.searchParams.get('template'),paginationToken=await page.locator('#reports-workspace').getAttribute('data-csrf');
  const revisionUrl=base+`/api/reports/templates/${paginationId}/versions/1`;
  let paginationRevision=(await (await page.request.get(revisionUrl)).json()).item;
  const printLayout={schema_version:1,page:{format:'A5',orientation:'landscape',margin_top:10,margin_right:10,margin_bottom:12,margin_left:20,number_pages:true},body:[
    {id:'intro',type:'section',props:{pagination:{keep_together:true}},children:[{id:'caption',type:'text',props:{text:'Relatório de paginação',level:'title'}},{id:'logo',type:'image',props:{source:'data:image/png;base64,'+logoFile.buffer.toString('base64'),alt:'Logotipo',width:24,height:12}}]},
    {id:'grid',type:'section',props:{columns:2,gap:8,pagination:{keep_together:true}},children:[{id:'left',type:'text',props:{text:'Coluna esquerda'}},{id:'right',type:'text',props:{text:'Coluna direita'}}]},
    {id:'rows',type:'table',props:{collection:{source:'data',path:['items']},columns:[{label:'Descrição',binding:{source:'item',path:['name']}},{label:'Valor',binding:{source:'item',path:['amount']},aggregate:'sum',format:{kind:'number',decimals:1}}]}},
    {id:'finish',type:'text',props:{text:'Fechamento final',pagination:{break_before:true}}}
  ]};
  const items=Array.from({length:100},(_,index)=>({name:'ITEM_'+String(index+1).padStart(3,'0'),amount:index+0.5}));
  async function savePrintLayout() {
    const response=await page.request.put(revisionUrl,{headers:{'X-Reports-CSRF':paginationToken},data:{lock_version:paginationRevision.lock_version,layout:printLayout,data_schema:{type:'object',properties:{items:{type:'array',items:{type:'object',properties:{name:{type:'string'},amount:{type:'number'}},required:['name','amount']}}},required:['items']},sample_data:{items},parameters:[]}});
    assert.equal(response.status(),200);paginationRevision=(await response.json()).item;
    const preview=await page.request.post(revisionUrl+'/preview',{headers:{'X-Reports-CSRF':paginationToken},data:{format:'html',parameters:{}}});assert.equal(preview.status(),200);return (await preview.json()).html;
  }
  const paginated=await browser.newPage();
  for(const [name,format,orientation] of [['landscape','A5','landscape'],['portrait','A4','portrait']]) {
    printLayout.page.format=format;printLayout.page.orientation=orientation;
    await paginated.setContent(await savePrintLayout());await paginated.locator('img').evaluate(image=>image.decode());
    await paginated.evaluate(()=>document.documentElement.dataset.theme='dark');await paginated.emulateMedia({media:'print'});
    assert.equal(await paginated.locator('.report-document').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(255, 255, 255)');
    assert.equal(await paginated.locator('tfoot').textContent(),'5.000,0');
    const output=await paginated.pdf({preferCSSPageSize:true,printBackground:true,displayHeaderFooter:false});
    if(process.env.REPORTS_SCREENSHOTS){fs.mkdirSync(process.env.REPORTS_SCREENSHOTS,{recursive:true});fs.writeFileSync(process.env.REPORTS_SCREENSHOTS+'/reports-pagination-'+name+'.pdf',output);}
  }
  await paginated.close();
  await page.goto(base+'/reports/');
  for(const name of ['receita-completa','sessao-detalhada','estoque-atual','estoque-organizacional','banco-leveduras','dashboard-geral','disponibilidade-validade','planejamento-starters','checklist-receita']) {
    await page.locator('#ready-template').selectOption(name);await page.locator('#create-ready-template').click();await state('saved');
    await page.waitForFunction(name=>document.querySelector('#report-example').value===name,name);
    await page.waitForFunction(()=>!document.querySelector('#load-library-data').disabled && !document.querySelector('#create-ready-template').disabled);
    if(['receita-completa','checklist-receita','sessao-detalhada','estoque-organizacional'].includes(name)) {
      await page.locator('#refresh-library-records').click();
      await page.waitForFunction(()=>document.querySelector('#library-record').options.length>1 && !document.querySelector('#refresh-library-records').disabled);
      const option=name==='estoque-organizacional'?{organization_code:fixtures.organization_code}:name==='sessao-detalhada'?{session_id:fixtures.session_id,plant_id:fixtures.plant_id}:{recipe_id:fixtures.recipe_id};
      const selected=await page.locator('#library-record option').evaluateAll((nodes,expected)=>nodes.find(node=>{try{const value=JSON.parse(node.value);return Object.keys(expected).every(key=>value[key]===expected[key]);}catch{return false;}})?.value,option);
      assert.ok(selected);await page.locator('#library-record').selectOption(selected);
    }
    await page.locator('#load-library-data').click();await state('dirty');
    await page.locator('#preview-report').click();await state('preview');
    assert.equal(await page.frameLocator('#html-preview').locator('table').count()>0,true);
    if(name==='receita-completa')assert.equal(await page.frameLocator('#html-preview').getByText('Receita real de teste',{exact:true}).count(),1);
    if(name==='estoque-atual')assert.equal(await page.frameLocator('#html-preview').getByText('REPORTS-TEST',{exact:true}).count(),1);
    if(process.env.REPORTS_SCREENSHOTS) {
      fs.writeFileSync(process.env.REPORTS_SCREENSHOTS+'/library-'+name+'.html',await page.locator('#html-preview').getAttribute('srcdoc'));
      if(name==='receita-completa')await page.screenshot({path:process.env.REPORTS_SCREENSHOTS+'/reports-library-recipe.png',fullPage:true});
    }
    await page.waitForFunction(()=>!bootstrap.Modal.getInstance(document.getElementById('reports-preview'))._isTransitioning);
    await page.locator('#reports-preview .btn-close').click();await page.locator('#reports-preview').waitFor({state:'hidden'});
    await publish();
  }
  for(const [screen,source,initial] of [['receitas','receita-completa',`recipe_id=${fixtures.recipe_id}`],['sessoes','sessao-detalhada',`session_id=${fixtures.session_id}&plant_id=${fixtures.plant_id}`],['banco-leveduras','banco-leveduras',''],['disponibilidade-validade','disponibilidade-validade',''],['starters','planejamento-starters',''],['dashboard','dashboard-geral',''],['estoque','estoque-organizacional',`organization_code=${fixtures.organization_code}`]]) {
    await page.goto(base+'/'+(screen==='estoque'?'estoque':'brewstation')+'/reports/'+screen+'?'+initial);
    await page.waitForFunction(()=>!document.querySelector('#emission-generate').disabled);
    await page.locator('#emission-template').selectOption('ready.'+source);
    if(['receitas','sessoes','estoque'].includes(screen))assert.ok(await page.locator('#emission-record').inputValue());
    await page.locator('#emission-generate').click();
    await page.waitForFunction(()=>!document.querySelector('#emission-print').disabled);
    assert.ok((await page.frameLocator('#emission-preview').locator('main').textContent()).trim());
    await page.locator('#emission-preview').evaluate(frame=>{frame.contentWindow.print=()=>{frame.dataset.printCalled='true';};});
    await page.locator('#emission-print').click();assert.equal(await page.locator('#emission-preview').getAttribute('data-print-called'),'true');
    if(process.env.REPORTS_SCREENSHOTS)await page.screenshot({path:process.env.REPORTS_SCREENSHOTS+'/emission-'+screen+'.png',fullPage:true});
    if(screen==='estoque'){await page.locator('#emission-positive_only').check();assert.equal(await page.locator('#emission-print').isDisabled(),true);}
  }
  await page.goto(base+fixtures.session_url);const sessionLink=page.locator('a[href*="/brewstation/reports/sessoes?"]');
  assert.ok((await sessionLink.getAttribute('href')).includes('session_id='+fixtures.session_id));
  await sessionLink.click();await page.waitForURL('**/brewstation/reports/sessoes?**');
  await page.waitForFunction(()=>Boolean(document.querySelector('#emission-record')?.value));
  await page.waitForFunction(()=>!document.querySelector('#emission-generate').disabled);
  assert.ok(page.url().includes('session_id='+fixtures.session_id));
  assert.equal((await page.request.post(base+'/api/auth/update-theme',{data:{theme:'dark'}})).status(),200);
  await page.reload();await page.waitForFunction(()=>!document.querySelector('#emission-generate').disabled);
  await page.locator('#emission-template').selectOption('ready.sessao-detalhada');await page.locator('#emission-generate').click();
  await page.waitForFunction(()=>!document.querySelector('#emission-print').disabled);
  assert.equal(await page.frameLocator('#emission-preview').locator('.report-document').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(39, 53, 73)');
  if(process.env.REPORTS_SCREENSHOTS)await page.screenshot({path:process.env.REPORTS_SCREENSHOTS+'/emission-dark.png',fullPage:true});
  assert.deepEqual(errors,[]);await browser.close();
  console.log('Reports IDE, themes, print, conflict and consumer HTML/print passed');
})().catch(error=>{console.error(error);process.exit(1)});
