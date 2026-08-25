# 22 — Fusão de Starter em BankEvent + Contagem↔Evento + campos de Neubauer

> **Status: [EXECUTADO] (2026-08-24).** Continuação direta da skill
> 21 — Christopher testou o Painel de verdade e voltou com uma
> reconsideração de schema: `YeastStarterLog`
> deixa de existir como tabela própria, funde totalmente em
> `YeastBankEvent`. Junto, dois achados de pesquisa de domínio (câmara
> de Neubauer) viram campo novo. Mesma convenção de status das skills
> 05/19/21.

---

## 0. Motivação

Christopher, usando o Painel de verdade: *"a contagem não depende de
starter + o starter deverá ter estimativa de contagem"* — confirma que
a decisão da skill 21 (remover `starter_id` de `CellCountHistory`) foi
certa, mas expõe uma lacuna nova: o Starter em si não tem nenhum campo
de estimativa de célula, e a estrutura de 3 tabelas (Event/Starter/
CellCount) ficou mais pesada do que o uso real pede. Proposta dele:
fundir Starter dentro do Evento, e ligar Contagem de Células ao
Evento diretamente (não só ao Item).

## 1. `YeastStarterLog` — removida, fundida em `YeastBankEvent`

**[DECIDIDO]** Escolhida a opção B (fusão total) entre as duas
apresentadas — a alternativa "aditiva" (manter `YeastStarterLog`
separada, só somar um campo de estimativa) foi descartada
explicitamente pelo Christopher.

### 1.1 Schema — `YeastBankEvent` (campos novos, vindos do Starter)

| Campo novo | Tipo | Só preenchido quando |
|---|---|---|
| `brew_date` | Date, nullable | `event_type="Starter"` |
| `start_date` | Date, nullable | `event_type="Starter"` |
| `target_volume_l` | Float, nullable | `event_type="Starter"` |
| `objective` | String(30), nullable | `event_type="Starter"` |
| `starter_status` | String(30), nullable | `event_type="Starter"` |
| `result_viability_percent` | Float, nullable | `event_type="Starter"` |
| `contamination_detected` | Boolean, default `false` | `event_type="Starter"` |
| `estimated_cells_per_ml` | Float, nullable | `event_type="Starter"` — **novo**, não existia no Starter antigo; é a "estimativa de contagem" que o Christopher pediu (achismo rápido, não é uma contagem formal de Neubauer) |

**`starter_status` e não `status`** — achado real ao desenhar a fusão:
`YeastBankEvent` já tem `status_before`/`status_after` (transição do
*Item* quando o evento é Descarte). O Starter tinha seu próprio
`status` (fluxo da propagação em si — outro conceito). Reaproveitar o
nome `status` colidiria semanticamente; `starter_status` deixa os dois
conceitos claramente separados na mesma tabela.

`starter_id` (a FK que ligava o evento ao registro de Starter
separado) é **removida** — não tem mais pra onde apontar.

### 1.2 O que muda no fluxo de criação (`post_create_redirect`)

Antes: `event_type="Starter"` criava um `YeastStarterLog` novo e
redirecionava pra edição dele. Depois: `event_type="Starter"` não
cria mais registro nenhum — os campos específicos (`brew_date`,
`target_volume_l`, etc.) já fazem parte do próprio formulário do
Evento, preenchidos na hora de criar ou editados depois na mesma
tela. Sem redirecionamento pra tela nenhuma nesse caso — mesmo
comportamento que "Descarte"/"Outro" já têm hoje.

`event_type="Contagem de Células"` continua criando o registro
especializado e redirecionando — `CellCountHistory` continua
tabela própria (seção 2 justifica o porquê).

### 1.3 [ABERTO] Dado existente

Não há `YeastStarterLog` real cadastrado em produção ainda (a Feature
está em uso recente) — migration de dado não deve ser necessária, mas
a migration de schema precisa checar e recusar avançar se encontrar
linha existente, em vez de simplesmente descartar silenciosamente
(mesmo padrão defensivo das migrations anteriores).

## 2. Por que `CellCountHistory` continua tabela própria (não funde também)

Diferente do Starter, a Contagem de Células ganha um bloco de campos
de entrada bruta (seção 3) específico da câmara de Neubauer — inserir
isso dentro de `YeastBankEvent` reproduziria exatamente o problema de
"tabela esparsa" que a skill 21 já evitou de propósito (colunas que só
fazem sentido pra 1 dos 4 tipos de evento). Em vez de fundir, ganha um
vínculo direto:

### 2.1 Schema — `YeastCellCountHistory` (campo novo)

| Campo novo | Tipo | Papel |
|---|---|---|
| `bank_event_id` | Integer, FK → `bank_event.id`, nullable | Rastreia qual Evento originou esta contagem — hoje só dava pra saber pelo `bank_item_id` (perdendo a informação de "qual dos vários eventos desse item gerou qual contagem") |

Preenchido automaticamente pelo mesmo `post_create_redirect` que já
cria o registro — não é escolhido manualmente (`@readonly_fields`,
mesmo padrão do `starter_id`/`cell_count_id` de antes).

## 3. Campos de Neubauer — `YeastCellCountHistory`

Pesquisa de domínio (câmara de Neubauer/hemocitômetro, prática padrão
de contagem de levedura): a área central tem 1mm² × 0,1mm de altura
(0,1mm³), dividida em 25 quadrados médios; a prática padrão conta 5
desses quadrados (4 cantos + o central) e extrapola. Fórmula usada na
prática cervejeira:

```
células/mL = (soma das células contadas nos 5 quadrados) × 5 × fator de diluição × 10.000
viabilidade % = vivas × 100 / (vivas + mortas)
células viáveis/mL = células/mL × viabilidade% / 100
```

### 3.1 Schema — campos novos (entrada bruta)

| Campo novo | Tipo | Papel |
|---|---|---|
| `cells_counted_live` | Integer, nullable | Células vivas contadas nos quadrados |
| `cells_counted_dead` | Integer, nullable | Células mortas contadas |
| `squares_counted` | Integer, nullable, default `5` | Quantos quadrados foram usados (padrão 5 — a prática comum) |
| `dilution_factor` | Float, nullable, default `1` | Fator de diluição da amostra |

Os 3 campos de **resultado** que já existem (`cells_per_ml`,
`viability_percent`, `viable_cells_per_ml`) continuam existindo e
editáveis diretamente — pra quem já calculou por fora, ou dado
migrado antigo. Um hook novo (`yeast_cell_count_history_service_hooks.py`,
mesmo padrão do `_auto_fill_expiry_date`) calcula os 3 automaticamente
a partir dos campos brutos **só quando os brutos vêm preenchidos e os
de resultado não** — nunca sobrescreve valor já informado manualmente.

### 3.2 Fórmula exata (pra implementação)

```python
total = cells_counted_live + cells_counted_dead
cells_per_ml = total * (25 / squares_counted) * dilution_factor * 10_000
viability_percent = (cells_counted_live * 100) / total  # se total > 0
viable_cells_per_ml = cells_per_ml * viability_percent / 100
```

Proteção óbvia: `total == 0` não pode gerar divisão por zero —
`viability_percent` fica `None` nesse caso (não dá pra calcular
viabilidade sem nenhuma célula contada, viva ou morta).

## 4. Documentação exigida

Mesma exigência já registrada na skill 21 — manual + fluxos técnicos
tocados na implementação:

- `docs/manual/03-funcionalidades.md` — Starter deixa de ser entidade
  própria no texto, vira "os campos que aparecem quando o evento é
  tipo Starter"; nova seção explicando os campos de contagem bruta
  (em linguagem de usuário, sem citar "Neubauer" tecnicamente demais
  — algo como "quantas células vivas/mortas você contou, e o sistema
  calcula sozinho").
- `docs/technical/03-fluxos.md` — fluxo do `post_create_redirect`
  atualizado (Starter não redireciona mais pra lugar nenhum); fluxo
  novo do cálculo automático de Neubauer.
- `docs/technical/04-modelo-de-dados.md` — `YeastStarterLog` removida
  do ER; `YeastBankEvent`/`YeastCellCountHistory` atualizados com os
  campos novos.

## 5. O que fica fora desta skill

- Painel (JS) — precisa de ajuste pra refletir que Starter não é mais
  um registro separado (o botão "Abrir Starter" da skill 21/Fase 24
  deixa de fazer sentido; os campos do Starter aparecem direto no
  card do evento, não numa tela própria). Fica pra quando a
  implementação desta skill estiver pronta, mesmo patch ou o
  seguinte.
- Cálculo de viabilidade da Cepa (`viability_engine.py`) — não muda;
  `result_viability_percent` do Starter (agora em `BankEvent`)
  continua sendo a 3ª prioridade de referência, sem mudança de
  comportamento.
