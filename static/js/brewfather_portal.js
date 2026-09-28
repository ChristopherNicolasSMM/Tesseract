document.addEventListener('DOMContentLoaded', function () {
  // O hook do CrudGen fica numa barra oculta até marcar um log.
  // Coloca o acesso ao portal no cabeçalho, sempre visível.
  const portalLink = document.getElementById('bf-portal-link');
  const heading = document.querySelector('.pagetitle');
  if (portalLink && heading) {
    portalLink.classList.add('mt-2');
    heading.appendChild(portalLink);
  }
  document.querySelectorAll('[data-confirm-message]').forEach(bulkForm => {
    bulkForm.addEventListener('submit', event => {
      if (!window.confirm(bulkForm.dataset.confirmMessage)) event.preventDefault();
    });
  });
  const form = document.getElementById('bf-selecao-form');
  if (!form) return;
  const items = Array.from(form.querySelectorAll('.bf-item'));
  const all = document.getElementById('bf-todas');
  const count = document.getElementById('bf-contador');
  const submit = document.getElementById('bf-sincronizar');
  const action = document.getElementById('bf-acao');
  function available(item) {
    return action.value === 'sincronizar'
      ? item.dataset.status !== 'ja_importada'
      : item.dataset.status === 'ja_importada';
  }
  function update() {
    items.forEach(item => { item.disabled = !available(item); if (item.disabled) item.checked = false; });
    const enabled = items.filter(available);
    const selected = items.filter(item => item.checked).length;
    count.textContent = selected + ' selecionada(s)';
    submit.disabled = selected === 0 || selected > 50;
    all.checked = enabled.length > 0 && selected === enabled.length;
    all.indeterminate = selected > 0 && selected < enabled.length;
    all.disabled = enabled.length === 0;
    if (selected > 50) count.textContent += ' — máximo de 50 por operação';
  }
  all.addEventListener('change', function () {
    items.forEach(item => { item.checked = !item.disabled && all.checked; });
    update();
  });
  items.forEach(item => item.addEventListener('change', update));
  action.addEventListener('change', () => { items.forEach(item => { item.checked = false; }); update(); });
  form.addEventListener('submit', function (event) {
    if (submit.disabled || (action.value === 'apagar' && !window.confirm('Mover as receitas selecionadas para a lixeira do Tesseract?'))) event.preventDefault();
  });
  update();
});
