# 14 — EventBus: Convenção de Evento e Contrato de Payload

> **Status: REFERÊNCIA DESCRITIVA — formaliza convenção já em uso,
> não inventa nada novo.** `core/event_bus.py` já existe desde a Fase
> 1 e já é usado por 2 pares publisher/subscriber reais — esta skill
> documenta o que já está em produção e aponta 2 achados reais de
> manutenção encontrados na revisão (seções 5 e 6), sem alterar
> comportamento.

---

## 1. API real

```python
from core.event_bus import event_bus

event_bus.subscribe("nome.do.evento", handler_function)
event_bus.publish("nome.do.evento", **payload)
```

- **Síncrono, em memória, processo único** — `publish()` chama cada
  handler diretamente, na mesma thread, na hora. Não é fila, não
  atravessa processo/rede. Decisão de fase (Fase 1): trocar por algo
  distribuído (Redis, etc.) só quando algum Addon precisar de
  verdade — não adiantar dependência.
- **Um handler com erro nunca derruba os outros** — `publish()` isola
  cada handler num `try/except` próprio; exceção vira `logger.exception`,
  não propaga. Um listener quebrado não impede os demais listeners do
  mesmo evento nem o publicador de continuar.
- **`subscribe()` é aditivo, não substitui** — chamar `subscribe()``
  duas vezes para o mesmo evento registra dois handlers, ambos rodam.
  Módulos que se inscrevem uma vez só no boot (padrão real: ver seção
  3) precisam de flag de idempotência própria (`_registered = False`
  no módulo) — o EventBus em si não impede inscrição duplicada.

---

## 2. Convenção de nome de evento

Já registrada na skill 00 (tabela de casing), reforçada aqui:
**namespace por ponto, presente do indicativo no domínio + passado na
ação** — `[modulo].[entidade].[acao_no_passado]`.

```
core.module.activated
device_manager.actor.value_changed
```

`[modulo]` é o nome do Addon/Feature/Core dono do dado que mudou
(quem publica), não de quem escuta — `device_manager.actor.value_changed`
é nomeado a partir de `addon_device_manager` (que publica), mesmo o
único assinante real hoje sendo `feature_mash_control`.

---

## 3. Catálogo real de eventos em uso (2 hoje)

| Evento | Publicado por | Assinado por | Payload |
|---|---|---|---|
| `core.module.activated` | `core/module_manager.py` (todo módulo, ao ativar) | `core/event_bus.py::register_example_listener` (exemplo, seção 6) | `module_name: str`, `module_type: str` |
| `device_manager.actor.value_changed` | `addons/addon_device_manager/root/services/device_service.py` | `addons/addon_brewstation/features/feature_mash_control/services/automation_engine.py` | `function_name: str \| None`, `value` |

Ambos cross-Addon (Core→exemplo; `device_manager`→`mash_control`,
Addons diferentes) — exatamente o caso de uso pretendido: o EventBus
é **o único canal permitido** de comunicação entre Addons diferentes
(skill 02, seção de FK entre módulos). Dentro do mesmo Addon,
comunicação direta (import de service, FK real) continua permitida
normalmente — EventBus não é obrigatório ali, só uma opção a mais se
o desacoplamento for desejado mesmo assim.

---

## 4. Contrato de payload — sempre primitivo, nunca ORM

Regra já aplicada nos 2 casos reais, formalizada aqui: o payload de
`publish()` é sempre tipo primitivo (`str`, `int`, `float`, `bool`,
`None`, ou combinação simples em `dict`/`list`) — **nunca** o objeto
ORM (`DeviceActor`, `Transaction`, etc.) em si, mesmo para quem só vai
ler. Motivo: quem assina não pode enxergar o model interno de outro
módulo — a mesma regra de fronteira que já vale para qualquer service
público cross-Addon (skill 02).

```python
# CERTO — device_service.py
function_name = actor.function.name if actor.function else None
event_bus.publish(EVENT_ACTOR_VALUE_CHANGED, function_name=function_name, value=value)

# ERRADO — vazaria o ORM de addon_device_manager pra quem assina
event_bus.publish(EVENT_ACTOR_VALUE_CHANGED, actor=actor)
```

---

## 5. [ABERTO] Achado: nome do evento duplicado como string literal

`EVENT_ACTOR_VALUE_CHANGED = "device_manager.actor.value_changed"` é
declarada **duas vezes**, independentemente — uma em
`device_service.py` (quem publica), outra em `automation_engine.py`
(quem assina). Não há import compartilhado de uma constante única.
Funciona hoje porque as duas cópias batem, mas é um risco real de
deriva silenciosa: renomear o evento num lado sem lembrar do outro não
dá erro nenhum, só para de funcionar (o `publish()` de um nome que
ninguém assina não avisa, e o `subscribe()` de um nome que ninguém
publica também não).

**Não resolvido nesta rodada** — duas saídas possíveis, nenhuma
decidida:
1. Catálogo central de nomes de evento (ex.: `core/events_catalog.py`,
   mesmo espírito de `core/rules_catalog.py`/`core/transactions_catalog.py`)
   — Addon publicador declara a constante lá, quem assina importa de
   lá também.
2. Aceitar a duplicação como o preço do desacoplamento real entre
   Addons (importar de um catálogo central ainda é uma forma de
   acoplamento, mesmo que leve) — manter como está, só documentado.

## 6. [ABERTO] Achado: docstring desatualizada em `register_example_listener()`

`core/event_bus.py::register_example_listener()` tem o comentário
*"Remover quando o primeiro Addon real (Fase 5) tiver seus próprios
listeners"* — isso já aconteceu (`device_manager`/`mash_control`,
seção 3), o listener de exemplo continua registrado no boot mesmo
assim. Não removido nesta rodada (é código, não documentação) —
registrado aqui pra quando o BACKLOG for retomado.
