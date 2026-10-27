(() => {
  'use strict';

  const api = '/api/device-manager/communication';
  const $ = (id) => document.getElementById(id);
  let actors = [];
  let brokerEnabled = false;

  function setMessage(id, message, ok = true) {
    const node = $(id);
    node.textContent = message || '';
    node.className = `small mt-2 ${ok ? 'text-success' : 'text-danger'}`;
  }

  async function post(path, body = {}) {
    const response = await fetch(`${api}/${path}`, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(body),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok && !result.message) result.message = `HTTP ${response.status}`;
    return result;
  }

  function fmtTime(value) {
    if (!value) return 'Sem recebimento';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
  }

  function cell(row, value, className = '') {
    const td = row.insertCell();
    td.textContent = value == null || value === '' ? '—' : String(value);
    if (className) td.className = className;
    return td;
  }

  function fillSelect(id, options, firstLabel) {
    const select = $(id);
    const prior = select.value;
    select.replaceChildren(new Option(firstLabel, ''));
    options.forEach(({ id: value, label, disabled = false }) => {
      const option = new Option(label, value);
      option.disabled = Boolean(disabled);
      select.add(option);
    });
    if ([...select.options].some((option) => option.value === prior)) select.value = prior;
  }

  function renderActors() {
    const body = $('actor-table');
    body.replaceChildren();
    if (!actors.length) {
      const row = body.insertRow();
      cell(row, 'Nenhum ator cadastrado.', 'text-muted');
      row.cells[0].colSpan = 6;
      return;
    }
    actors.forEach((actor) => {
      const row = body.insertRow();
      cell(row, actor.name);
      cell(row, [actor.device_name, actor.function_label || actor.function_name].filter(Boolean).join(' / '));
      cell(row, actor.actor_type + (actor.is_risk ? ' · risco' : ''));
      const observation = actor.observation;
      cell(row, observation ? JSON.stringify(observation.value) :
        (actor.state_topic ? (brokerEnabled ? `Aguardando MQTT · ${actor.state_topic}` : 'MQTT desativado') : 'Sem state_topic'));
      cell(row, fmtTime(observation && observation.observed_at));
      const actions = row.insertCell();
      actions.className = 'text-nowrap';
      [
        ['actor', 'bi-pencil-square', 'Abrir ator'],
        ['device', 'bi-cpu', 'Abrir dispositivo'],
        ['function', 'bi-sliders', 'Abrir função'],
      ].forEach(([key, icon, title]) => {
        if (!actor.links || !actor.links[key]) return;
        const link = document.createElement('a');
        link.className = 'btn btn-sm btn-outline-secondary me-1';
        link.href = actor.links[key];
        link.title = title;
        link.setAttribute('aria-label', title);
        const glyph = document.createElement('i'); glyph.className = `bi ${icon}`;
        link.append(glyph); actions.append(link);
      });
      const choose = document.createElement('button');
      choose.type = 'button';
      choose.className = 'btn btn-sm btn-outline-primary select-actor-test';
      choose.dataset.actorId = actor.id;
      choose.innerHTML = '<i class="bi bi-crosshair"></i> Testar';
      actions.append(choose);
    });

    const actuators = actors.filter((actor) => actor.actor_type === 'actuator' && actor.command_topic);
    fillSelect('command-actor', actuators.map((actor) => {
      const protectedActor = actor.is_risk || hasBridge(actor);
      const inactive = !actor.is_active || !actor.device_active;
      const reason = protectedActor ? ' · envio protegido via Mash Control' : inactive ? ' · inativo' : '';
      return { id: actor.id, label: `${actor.name} · ${actor.command_topic}${reason}`, disabled: protectedActor || inactive };
    }), 'Selecione um atuador…');
    fillSelect('mqtt-test-actor', actors.map((actor) => {
      const topic = actor.command_topic || actor.state_topic;
      const role = actor.actor_type === 'actuator' ? 'atuador' : 'sensor';
      return { id: actor.id, label: `${actor.name} · ${role} · ${topic || 'sem tópico MQTT'}` };
    }), 'Sem ator — informar tópico manualmente');
    const bridgeActors = actors.filter(hasBridge);
    const bridgeActuators = bridgeActors.filter((actor) => actor.actor_type === 'actuator' && actor.is_active && actor.device_active && actor.command_topic);
    fillSelect('bridge-actor', bridgeActuators.map((actor) => ({ id: actor.id, label: `${actor.name} · ${bridgeKind(actor)}` })), 'Selecione um ator Bridge…');

    const bridgeBody = $('bridge-table');
    bridgeBody.replaceChildren();
    if (!bridgeActors.length) {
      const row = bridgeBody.insertRow(); cell(row, 'Nenhuma telemetria Bridge associada aos atores.', 'text-muted'); row.cells[0].colSpan = 5;
    } else {
      bridgeActors.forEach((actor) => {
        const row = bridgeBody.insertRow();
        const bridge = actor.bridge || {};
        const telemetry = bridge.control || bridge.heating || bridge.source || {};
        const ack = bridge.control && bridge.control.last_command;
        cell(row, actor.name);
        cell(row, `${bridgeKind(actor)}${telemetry.external_policy ? ` · ${telemetry.external_policy}` : ''}`);
        cell(row, bridgeState(telemetry, actor));
        cell(row, ack ? `${ack.status}: ${ack.message || ack.request_id}` : 'Sem ACK recente');
        cell(row, fmtTime(telemetry.received_at || telemetry.observed_at));
      });
    }
  }

  function hasBridge(actor) {
    const bridge = actor.bridge || {};
    return Boolean(bridge.detected || bridge.control || bridge.heating || bridge.source);
  }
  function bridgeKind(actor) {
    const bridge = actor.bridge || {};
    const kind = bridge.control?.kind || (bridge.source ? 'fonte' : bridge.heating ? 'aquecimento' : bridge.kind);
    return ({ power: 'potência', pump: 'bomba', source: 'fonte', heating: 'aquecimento', gateway_mqtt: 'Gateway MQTT' })[kind] || 'Bridge';
  }
  function bridgeState(value, actor) {
    if (!value || !Object.keys(value).length) return brokerEnabled ? 'Aguardando telemetria Bridge' : 'MQTT desativado';
    const data = [];
    if (value.output_on !== undefined) data.push(value.output_on ? 'ligado' : 'desligado');
    if (value.temperature !== undefined) data.push(`${value.temperature}°`);
    if (value.target !== undefined) data.push(`alvo ${value.target}°`);
    if (value.fault) data.push(`falha: ${value.fault}`);
    if (value.pending_confirmation) data.push('confirmação pendente');
    return data.join(' · ') || value.owner || 'Telemetria recebida';
  }

  function selectActorForTest(actorId) {
    const actor = actors.find((item) => String(item.id) === String(actorId));
    if (!actor) return;
    const bridgeTab = hasBridge(actor) && actor.actor_type === 'actuator';
    if (bridgeTab) {
      $('bridge-actor').value = String(actor.id);
      const control = actor.bridge && actor.bridge.control;
      if (control?.kind === 'power') $('bridge-action').value = 'power_prepare';
      if (control?.kind === 'pump') $('bridge-action').value = 'pump_set';
      window.bootstrap?.Tab.getOrCreateInstance(document.querySelector('[data-bs-target="#mash-pane"]')).show();
      $('bridge-output').textContent = `Ator selecionado: ${actor.name}. O envio exige telemetria Bridge recente.`;
      return;
    }
    if ([...$('command-actor').options].some((option) => option.value === String(actor.id))) {
      $('command-actor').value = String(actor.id);
    }
    const topic = actor.state_topic ? ` Tópico de estado: ${actor.state_topic}.` : '';
    $('selected-actor-context').textContent = `Ator selecionado: ${actor.name}.${topic} A recepção aparece nesta visão quando chegar uma mensagem no state_topic.`;
    window.bootstrap?.Tab.getOrCreateInstance(document.querySelector('[data-bs-target="#mqtt-pane"]')).show();
  }

  async function refresh() {
    try {
      const response = await fetch(`${api}/status`, { credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const state = await response.json();
      actors = state.actors || [];
      const broker = state.broker || {};
      brokerEnabled = Boolean(broker.enabled);
      $('mqtt-status').textContent = broker.enabled ? (broker.connected ? 'Conectado' : 'Desconectado') : 'Desativado';
      $('mqtt-status').className = `fs-5 fw-semibold ${broker.connected ? 'text-success' : 'text-warning'}`;
      $('mqtt-meta').textContent = `${broker.host || '—'}:${broker.port || '—'} · client_id ${broker.client_id || '—'} · prefixo ${broker.topic_prefix || '—'}`;
      $('actors-count').textContent = `${actors.length} ator(es) · ${actors.filter((actor) => actor.observation).length} com estado recebido`;
      renderActors();
    } catch (error) {
      $('mqtt-status').textContent = 'Não foi possível ler o status';
      $('mqtt-meta').textContent = error.message;
    }
  }

  $('refresh-status').addEventListener('click', refresh);
  $('actor-table').addEventListener('click', (event) => {
    const button = event.target.closest('.select-actor-test');
    if (button) selectActorForTest(button.dataset.actorId);
  });
  $('mqtt-test-actor').addEventListener('change', (event) => {
    const actor = actors.find((item) => String(item.id) === event.currentTarget.value);
    if (!actor) {
      $('mqtt-test-actor-hint').textContent = 'Sem ator selecionado. Informe qualquer tópico MQTT manualmente.';
      return;
    }
    const suggestedTopic = actor.command_topic || actor.state_topic;
    if (suggestedTopic) $('mqtt-test-topic').value = suggestedTopic;
    $('mqtt-test-actor-hint').textContent = suggestedTopic
      ? `Tópico sugerido para ${actor.name}. Você pode editá-lo antes de publicar.`
      : `${actor.name} não tem tópico MQTT configurado. Informe o tópico manualmente.`;
  });
  $('mqtt-probe').addEventListener('click', async (event) => {
    const button = event.currentTarget;
    button.disabled = true; $('mqtt-probe-output').textContent = 'Testando conexão, subscribe, publish e retorno…';
    try {
      const result = await post('mqtt/probe');
      setMessage('mqtt-probe-output', `${result.message || 'Teste concluído.'}${result.topic ? ` Tópico: ${result.topic}` : ''}`, result.success);
      $('last-result').textContent = result.success ? 'MQTT passou' : 'MQTT falhou';
      $('last-result-meta').textContent = result.message || '';
      await refresh();
    } catch (error) { setMessage('mqtt-probe-output', error.message, false); }
    finally { button.disabled = false; }
  });

  $('send-command').addEventListener('click', async (event) => {
    let value;
    try { value = JSON.parse($('command-value').value); }
    catch (_) { setMessage('command-output', 'Valor precisa ser JSON válido (por exemplo true, 25 ou "texto").', false); return; }
    const button = event.currentTarget; button.disabled = true;
    try {
      const result = await post('mqtt/command', { actor_id: $('command-actor').value, value, confirmed: $('command-confirm').checked });
      setMessage('command-output', `${result.message || 'Comando enviado.'}${result.topic ? ` Tópico: ${result.topic}` : ''}`, result.success);
      $('last-result').textContent = result.success ? 'Comando publicado' : 'Comando recusado';
      $('last-result-meta').textContent = result.message || '';
    } catch (error) { setMessage('command-output', error.message, false); }
    finally { button.disabled = false; }
  });

  $('mqtt-test-publish').addEventListener('click', async (event) => {
    const payload = $('mqtt-test-payload').value;
    if ($('mqtt-test-format').value === 'json') {
      try { JSON.parse(payload); }
      catch (_) { setMessage('mqtt-test-output', 'O payload precisa ser JSON válido.', false); return; }
    }
    const button = event.currentTarget; button.disabled = true;
    try {
      const result = await post('mqtt/publish', {
        topic: $('mqtt-test-topic').value,
        payload,
        payload_format: $('mqtt-test-format').value,
        qos: Number($('mqtt-test-qos').value),
        retain: $('mqtt-test-retain').checked,
        confirmed: $('mqtt-test-confirm').checked,
      });
      setMessage('mqtt-test-output', `${result.message || 'Publicação concluída.'}${result.full_topic ? ` Tópico efetivo: ${result.full_topic}` : ''}`, result.success);
      $('last-result').textContent = result.success ? 'MQTT publicado' : 'Publicação MQTT recusada';
      $('last-result-meta').textContent = result.message || '';
    } catch (error) { setMessage('mqtt-test-output', error.message, false); }
    finally { button.disabled = false; }
  });

  $('rest-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = $('rest-send'); button.disabled = true; $('rest-message').textContent = 'Enviando…';
    $('rest-result-card').classList.add('d-none');
    try {
      const result = await post('rest/request', {
        url: $('rest-url').value, method: $('rest-method').value,
        headers: $('rest-headers').value, body: $('rest-body').value,
      });
      if (!result.status) throw new Error(result.message || 'Falha na chamada REST.');
      $('rest-status').textContent = `${result.status}${result.redirect_blocked ? ' · redirecionamento bloqueado' : ''}`;
      $('rest-status').className = `badge ${result.success ? 'bg-success' : 'bg-danger'}`;
      $('rest-time').textContent = `${result.elapsed_ms} ms${result.truncated ? ' · corpo truncado em 64 KB' : ''}`;
      $('rest-response-headers').textContent = JSON.stringify(result.headers || {}, null, 2);
      $('rest-response-body').textContent = result.body || '(corpo vazio)';
      $('rest-result-card').classList.remove('d-none');
      $('rest-message').textContent = 'Resposta recebida.';
      $('rest-message').className = `small ms-2 ${result.success ? 'text-success' : 'text-warning'}`;
      $('last-result').textContent = `REST ${result.status}`;
      $('last-result-meta').textContent = `${result.elapsed_ms} ms · ${result.url}`;
    } catch (error) {
      $('rest-message').textContent = error.message;
      $('rest-message').className = 'small ms-2 text-danger';
      $('last-result').textContent = 'REST falhou'; $('last-result-meta').textContent = error.message;
    } finally { button.disabled = false; }
  });

  $('bridge-send').addEventListener('click', async (event) => {
    const action = $('bridge-action').value;
    const rawValue = $('bridge-value').value.trim();
    let value = null;
    if (action === 'power_prepare') {
      value = Number(rawValue);
      if (!rawValue || !Number.isFinite(value)) { setMessage('bridge-output', 'Informe uma potência numérica entre 0 e 100%.', false); return; }
    } else if (action === 'pump_set') {
      if (!['true', 'false'].includes(rawValue.toLowerCase())) { setMessage('bridge-output', 'Para bomba, informe true ou false.', false); return; }
      value = rawValue.toLowerCase() === 'true';
    }
    const button = event.currentTarget; button.disabled = true;
    try {
      const result = await post('mqtt/bridge-command', { actor_id: $('bridge-actor').value, action, value, confirmed: $('bridge-confirm').checked });
      setMessage('bridge-output', `${result.message || 'Ação enviada.'}${result.request_id ? ` Request ID: ${result.request_id}` : ''}`, result.success);
      $('last-result').textContent = result.success ? 'Ação Mash Control publicada' : 'Ação Mash Control recusada';
      $('last-result-meta').textContent = result.message || '';
      await refresh();
    } catch (error) { setMessage('bridge-output', error.message, false); }
    finally { button.disabled = false; }
  });

  refresh();
  window.setInterval(refresh, 5000);
})();
