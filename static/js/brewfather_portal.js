document.addEventListener('DOMContentLoaded', function () {
  // O hook do CrudGen fica numa barra oculta até marcar um log.
  // Coloca o acesso ao portal no cabeçalho, sempre visível.
  const portalLink = document.getElementById('bf-portal-link');
  const heading = document.querySelector('.pagetitle');
  if (portalLink && heading) {
    portalLink.classList.add('mt-2');
    heading.appendChild(portalLink);
  }
  const form = document.getElementById('bf-selecao-form');
  if (!form) return;
  const items = Array.from(form.querySelectorAll('.bf-item'));
  const all = document.getElementById('bf-todas');
  const count = document.getElementById('bf-contador');
  const submit = document.getElementById('bf-sincronizar');
  function update() {
    const selected = items.filter(item => item.checked).length;
    count.textContent = selected + ' selecionada(s)';
    submit.disabled = selected === 0 || selected > 50;
    all.checked = items.length > 0 && selected === items.length;
    all.indeterminate = selected > 0 && selected < items.length;
    if (selected > 50) count.textContent += ' — máximo de 50 por operação';
  }
  all.addEventListener('change', function () {
    items.forEach(item => { item.checked = all.checked; });
    update();
  });
  items.forEach(item => item.addEventListener('change', update));
  form.addEventListener('submit', function (event) {
    if (submit.disabled) event.preventDefault();
  });
  update();
});
