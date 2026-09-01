# 26 — Proposta: Reestruturação de Envase, Consumo de Insumo na Brassagem e Custo de Industrialização

> **Status: [EXECUTADO] (2026-09-01).** Implementado e testado —
> `Envase.material_resultante_id`, `BrewSession.insumos_baixados_em`/
> `custo_total_insumos`, `ingredient_consumption_service.py` novo,
> `envase_estoque_service.registrar_envase()` reescrito (Composição em
> vez de `ItemEnvase` digitado à mão), `calcular_custo_industrializacao_envase()`,
> botão "Confirmar Ingredientes" (gatilho decidido: ação explícita, não
> automática na mudança de status — ver seção 2.3, fechada nesta
> rodada). `ItemEnvase` mantido só como histórico (tabela não apagada,
> só parou de receber INSERT novo). 22 testes novos/reescritos
> (`tests/test_feature_envase.py`), suíte completa sem regressão.
>
> Nasceu de revisão de conceito pedida pelo Christopher: `Envase`/
> `ItemEnvase` (`feature_envase`) hoje exigem digitar
> manualmente quais materiais de embalagem entraram em cada envase,
> quando essa informação já poderia vir da Composição (BOM) do
> Material resultante. O objetivo final é calcular e armazenar o custo
> real de industrialização de cada produto envasado (ex.: Growler 1L
> Valirian Pilsen), somando custo de insumo de receita (rateado pelo
> volume) + custo dos componentes não-cerveja (via Composição).
>
> Convenção de status igual às skills 05/19/24/25: **[DECIDIDO]**
> fechado, pronto pra executar quando autorizado. **[EXECUTADO]** já no
> código. **[ABERTO]** ainda sem decisão.

---

## 0. Motivação e mapeamento conceitual

Fluxo real que o sistema precisa suportar: uma `MashRecipe` é
planejada e uma `BrewSession` (lote) é iniciada a partir dela (já
conectado — `BrewSession.recipe_id` é FK real, mesma Feature). Ao
final da produção, um ou mais `Envase` são registrados daquele lote —
cada `Envase` deve apontar pro **Material resultante** (o produto
acabado, ex. "Growler 1L Valirian Pilsen"), não mais pra uma lista
solta de `ItemEnvase` digitados na hora.

A partir do Material resultante, o custo dos componentes não-cerveja
(rótulo, tampa, caixa, sanitização) é resolvido automaticamente via
**Composição** (`Composicao`, `addon_estoque`) desse Material — já é
exatamente um auto-relacionamento `material_pai_id` → N
`material_componente_id` com `quantidade`, sem precisar de tabela
nova. O custo da parte líquida (cerveja) vem da receita: soma do custo
dos insumos usados na `BrewSession` ÷ litros produzidos = custo por
litro, multiplicado pelo volume daquele Envase.

**Achado que muda o desenho original de `ItemEnvase`**: com o Material
resultante carregando a Composição, digitar manualmente "quais
materiais de embalagem entraram nesse envase" fica redundante — mesmo
raciocínio já aplicado no RFQ ("não redigitar o que já está declarado
em outro lugar", skill 24). `ItemEnvase` deixa de ser necessário como
tabela de entrada manual.

---

## 1. Infraestrutura já existente que resolve boa parte do desenho [confirmado, sem trabalho novo]

Investigação real (antes de propor qualquer schema novo) encontrou que
duas das peças que pareciam faltar **já estão implementadas**:

| Peça | Onde já existe | Papel no cálculo novo |
|---|---|---|
| Fator de conversão de unidade de compra → unidade-base (ex.: saco 25kg → kg) | `MaterialUnidade.fator_para_base` (skill 23, Fase 2) | Resolve o exemplo do Christopher (saco de 25kg por R$250 → R$10/kg) sem nenhuma coluna nova — a conversão já acontece uma vez na entrada (`registrar_movimentacao`). |
| Custo médio ponderado, já por unidade-base | `Saldo.custo_medio` — recalculado a cada entrada em `_aplicar_entrada()`: `(saldo_atual×custo_medio_atual + entrada×custo_entrada) / novo_saldo` | É a fonte de custo unitário pra qualquer componente da Composição — inclusive o fallback natural de "preço médio" quando não há valor explícito informado no momento do cálculo. |
| BOM/composição | `Composicao` (`material_pai_id`/`material_componente_id`/`quantidade`) | O Material resultante (ex. Growler 1L) é `material_pai`; rótulo/tampa/caixa são `material_componente`. |

Conclusão: **a "Lacuna 2" identificada na sessão de investigação (custo
via Composição) não precisa de schema novo** — só de um service novo
que percorre `Composicao` de um Material e soma
`quantidade × Saldo.custo_medio` de cada componente.

---

## 2. Consumo de insumo na brassagem — a peça que de fato não existia [EXECUTADO]

Achado: `feature_mash_control` **nunca chama `estoque_service`** —
diferente de `feature_envase`, que já dá baixa de estoque (com
`custo_unitario` real) ao registrar embalagem
(`envase_estoque_service.registrar_envase`), o consumo de
malte/lúpulo/levedura ao brassar uma receita **não desconta estoque
nem registra custo hoje**.

### 2.1 Fluxo decidido — baixa na brassagem, com fallback lazy no envase [EXECUTADO]

Dois momentos possíveis de baixa, com precedência clara:

1. **Momento ideal — brassagem**: uma função nova, espelhando
   `envase_estoque_service.registrar_envase()`, consome os insumos da
   receita (`RecipeIngredient.material_id` × `quantidade`) contra o
   estoque real, capturando `custo_unitario` de saída (mesmo campo já
   existente em `Movimentacao`). Chamada como ação própria vinculada à
   `BrewSession` — gatilho: botão "Confirmar Ingredientes" (ver seção 2.3).
2. **Fallback no envase**: ao registrar um `Envase` daquele lote, o
   sistema verifica se a baixa já ocorreu (via o flag da seção 2.2).
   Se sim, só importa/usa os custos já registrados. Se não, executa a
   baixa **naquele momento**, antes de prosseguir com o cálculo do
   Envase — nunca deixa o lote sem custo de insumo rastreado.

### 2.2 Rastreio de "já foi baixado" — decisão fechada: flag em `BrewSession` [EXECUTADO]

Duas opções foram avaliadas — **decidido: Opção Y**, flag local em
`BrewSession` (`addon_brewstation`), não campo novo em `Movimentacao`
(`addon_estoque`). Motivo: `Movimentacao` é ledger compartilhado por
todo o sistema — evitar acoplar um campo específico de "origem
brassagem" nele preserva o isolamento entre Addons (skill 02) e
mantém a decisão "já baixei os insumos desse lote" onde o conceito de
lote realmente mora.

Campo novo proposto: `BrewSession.insumos_baixados_em` (DateTime,
nullable — `None` = ainda não baixado). Setado no momento em que a
função de consumo (seção 2.1) roda com sucesso, seja na brassagem, seja
no fallback do envase.

### 2.3 Gatilho exato do "momento de brassar" [EXECUTADO — decidido pelo Christopher]

`BrewSession.status` já tem `draft/active/paused/completed/aborted`.
**Decisão fechada**: ação explícita separada — botão "Confirmar
Ingredientes" na tela do lote, **não** automática na transição de
status pra `active`. Implementado como rota própria
(`POST /brewstation/brew-sessions/<id>/confirmar-ingredientes`, hook
de controller) + card na tela de detalhe (hook de template,
`_detail_extra.html`, skill 25 extensão). O fallback da seção 2.1
continua cobrindo o caso de o operador chegar direto no envase sem
confirmar antes.

### 2.4 Cálculo separado de commit — "fazer e refazer os cálculos" [EXECUTADO]

Duas funções com papéis diferentes, não uma opção ou outra:

- **Preview/simulação** (pura, sem gravar nada): lê
  `RecipeIngredient.quantidade × Saldo.custo_medio`, pode rodar quantas
  vezes o usuário quiser, útil antes de decidir brassar.
- **Baixa/commit** (a da seção 2.1): só roda uma vez por lote,
  protegida pelo flag `insumos_baixados_em`.

---

## 3. Schema revisado de Envase [EXECUTADO]

### 3.1 `Envase` — campo novo

| Campo novo | Tipo | Observação |
|---|---|---|
| `material_resultante_id` | Integer, referência fraca (sem FK — `addon_estoque`, skill 02) | O produto acabado (ex. "Growler 1L Valirian Pilsen"). Resolvido via `material_lookup.get_material`, mesmo padrão já usado em `material_id` nos demais pontos de integração com `addon_estoque`. |

`quantidade_litros` continua existindo (volume produzido/envasado
naquele evento). A partir de `material_resultante_id` +
`quantidade_litros` ÷ `Material.volume_real` do resultante, o sistema
deriva quantas unidades físicas (garrafas/latas/growlers) aquele
Envase representa — sem precisar de campo próprio pra "quantidade de
unidades", é sempre calculado.

### 3.2 `ItemEnvase` — descontinuado [EXECUTADO]

Deixa de ser necessário como tabela de entrada manual — a baixa de
estoque dos componentes de embalagem passa a ser derivada
automaticamente da Composição do `material_resultante_id` ×
quantidade de unidades geradas (seção 3.1), no mesmo momento em que
`envase_estoque_service` já dava baixa manual hoje. **Migration de
depreciação, não de exclusão imediata** — dado histórico já gravado em
`ItemEnvase` não é apagado; a tabela só para de receber novos
registros. Decisão final sobre remoção física fica para quando o novo
fluxo estiver validado em produção.

### 3.3 Nova função de cálculo de custo do Envase [EXECUTADO]

Combina as duas fontes já mapeadas:

```
custo_cerveja_do_envase = (custo_total_insumos_do_lote / litros_produzidos_do_lote) × quantidade_litros_do_envase
custo_componentes = soma, pra cada Composicao do material_resultante, de (quantidade × Saldo.custo_medio do componente)
custo_total_industrializacao = custo_cerveja_do_envase + custo_componentes
```

`litros_produzidos_do_lote` = soma de `Envase.quantidade_litros` de
todos os Envases já registrados daquele `lote_id` (mesmo raciocínio já
usado hoje, sem campo novo em `BrewSession`).

---

## 4. Fora de escopo desta rodada [ABERTO, registrado pra futuro]

Investigação do projeto legado (`BrewStation`,
`calculadora.py`/`calculadora_brewfather.py`) confirmou que **nunca
existiu cálculo de física de brassagem** (OG/FG/IBU sempre vieram
prontos do BrewFather, nunca calculados localmente) — o escopo real
sempre foi custo, não fórmula cervejeira. Isso fecha a dúvida que
tinha ficado em aberto numa sessão anterior.

O legado também tinha uma camada de **precificação de venda** em cima
do custo de industrialização (% lucro, % margem de cartão, %
sanitização, % impostos → preço final de venda) — não faz parte do
escopo decidido nesta skill, mas é uma extensão natural (mais um
conjunto de percentuais aplicado sobre `custo_total_industrializacao`
da seção 3.3, sem exigir mudança no desenho de Envase/Composição já
fechado aqui). Registrado como item futuro, não bloqueia esta entrega.

---

## 5. Implementação real (2026-09-01)

Arquivos tocados na execução, pra referência rápida:

- `addons/addon_brewstation/features/feature_mash_control/model/brew_session.py`
  — `insumos_baixados_em`/`custo_total_insumos`.
- `addons/addon_brewstation/features/feature_envase/model/envase.py`
  — `material_resultante_id` (`@weak_ref`, sem FK).
- `migrations/versions/730e0d92ce65_skill26_consumo_insumo_material_.py`
  — as duas colunas acima, sem migração de dado (ambas nullable).
- `addons/addon_estoque/root/services/material_lookup.py` —
  `get_composicao(material_pai_id)` novo (ponto de acesso público
  cross-Addon, skill 02).
- `addons/addon_brewstation/features/feature_mash_control/services/ingredient_consumption_service.py`
  (novo) — `calcular_custo_insumos_receita()` (puro) e
  `confirmar_consumo_ingredientes()` (idempotente, best-effort por
  linha — mesmo padrão de `estoque_service.movimentar_estoque_em_massa`).
- `addons/addon_brewstation/features/feature_envase/services/envase_estoque_service.py`
  (reescrito) — `registrar_envase(lote_id, material_resultante_id,
  quantidade_litros, ...)` (assinatura nova, `itens` removido);
  `calcular_custo_industrializacao_envase(envase_id)` novo.
- `addons/addon_brewstation/features/feature_mash_control/controller/brew_sessions_hooks.py`
  — rota `POST /brewstation/brew-sessions/<id>/confirmar-ingredientes`.
- `addons/addon_brewstation/features/feature_mash_control/templates/brew_sessions/_detail_extra.html`
  — card "Confirmar Ingredientes" (hook de template, skill 25
  extensão — primeiro uso real desse hook fora de Materiais).
- `addons/addon_brewstation/features/feature_mash_control/i18n/pt_BR.json`
  — chave de confirmação nova.
- `tests/test_feature_envase.py` — reescrito por completo (16 testes:
  caminho feliz com Composição, validações, fallback de confirmação
  de insumo, idempotência, cálculo de custo, botão end-to-end).

**Quebra de compatibilidade assumida**: `registrar_envase()` mudou de
assinatura (não recebe mais `itens: list[dict]`, recebe
`material_resultante_id` no lugar) — não havia nenhum controller/rota
chamando essa função em produção ainda (confirmado antes de mexer),
só os testes antigos, que foram reescritos junto. Nenhum dado real
existente foi afetado — `ItemEnvase` continua na tabela pra qualquer
Envase criado antes desta mudança.
