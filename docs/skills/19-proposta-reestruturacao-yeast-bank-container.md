# 19 — Proposta: Reestruturação do Yeast Bank com a entidade Container

> **Status: [DECIDIDO], pendente de implementação (2026-08-20).** Nasceu
> de revisão de uso real do `feature_yeast_bank` — a hierarquia atual
> (Dispositivo ↔ Item do banco, FK direta) não tem nível intermediário
> para agrupar amostras fisicamente (caixa, estante, prateleira dentro
> de um freezer/geladeira), o que deixa a navegação entre dispositivo e
> item achatada demais para o volume real de uso. Convenção de status
> igual à skill 05 — **[DECIDIDO]** fechado e pronto pra executar quando
> autorizado, **[EXECUTADO]** já no código, **[ABERTO]** ainda sem
> decisão.
>
> Nenhuma linha de código foi alterada por este documento — é só a
> proposta de schema e migration. Implementação começa só depois de
> autorização explícita (ver skill 00/README raiz, convenção de "pode
> proceguir").

---

## 0. Motivação

Hoje `YeastBankItem.storage_device_id` aponta direto para
`YeastStorageDevice` — um freezer inteiro é a menor unidade de
localização que o sistema entende. Na prática, um freezer guarda várias
caixas/estantes com dezenas de itens cada, e não existe entidade que
represente esse agrupamento físico nem uma tela que liste "os itens
desta caixa". `storage_slot` (texto livre em `YeastBankItem`) tentava
cobrir isso, mas sem estrutura nem navegação — o dado existe, a tela
não.

## 1. Decisão raiz

**[DECIDIDO]** Nova entidade `YeastContainer` (tabela curta `container`)
entra entre `YeastStorageDevice` e `YeastBankItem`:

```
Dispositivo (1) ──< Container (1) ──< Item do banco
```

- Container é **sempre físico** — sem conceito de container virtual
  avaliado e descartado nesta fase (ver seção 6, ponto 2, para o
  histórico da decisão).
- Um Container pertence a exatamente 1 Dispositivo. Um Dispositivo pode
  ter N Containers.
- Um Item do banco pertence a exatamente 1 Container.
  `YeastBankItem.storage_device_id` é **removido** — o dispositivo de um
  item é sempre resolvido por `item.container.device`, nunca por FK
  direta duplicada.
- Ordem de cadastro obrigatória, enforçada por FK `NOT NULL` (não só
  sugestão de UI): Dispositivo → Cepa → Container → Item do banco.

## 2. Schema — `YeastContainer` (nova tabela)

Tabela curta `container` — sem colisão em todo `addon_brewstation`
(conferido: nenhum outro model do addon usa esse nome curto). Tabela
final: `tesseract_brewstation_yeastbank_container`.

| Campo | Tipo | Obrigatório | Observação |
|---|---|---|---|
| `id` | Integer, PK | Sim | Padrão skill 02 |
| `name` | String(120) | Sim | Nome de exibição — "Caixa 3", "Estante A" |
| `container_type` | String(40) | Sim | Via `@enum_field`: `Caixa` / `Estante` / `Prateleira` / `Outro` — mesmo padrão de `device_type` em `YeastStorageDevice` |
| `device_id` | Integer, FK → `storage_device.id` | Sim | FK real (mesma Feature, permitida pela skill 02) + `@weak_ref` para combo de busca assíncrona, mesmo padrão já usado em `bank_item.storage_device_id` hoje |
| `description` | Text | Não | |
| `is_deleted` / `deleted_at` | Boolean / DateTime | Sim | Soft-delete padrão CrudGen |
| `created_at` / `updated_at` | DateTime | Sim | Padrão skill 02 |

`@label("Container")`, `@plural("yeast_containers")`,
`@display_field("name")`.

## 3. Schema — alterações em `YeastBankItem`

| Campo | Mudança |
|---|---|
| `storage_device_id` | **Removido** (fase final da migration, seção 4) |
| `container_id` | **Novo** — Integer, FK → `container.id`, `NOT NULL`, com `@weak_ref` substituindo o combo que hoje aponta pra `storage_device_id` |
| `storage_slot` | Mantido sem mudança de tipo — só muda o **significado**: passa a ser posição dentro do Container (ex.: "gaveta 2", "posição 5"), não mais posição solta dentro do dispositivo inteiro |
| Todo o resto (`strain_id`, datas de viabilidade, `status`, etc.) | Sem mudança |

Nenhuma outra tabela do `feature_yeast_bank` muda —
`YeastStarterLog.bank_item_id`, `YeastCellCountHistory.bank_item_id`/
`starter_id` e `YeastBankEvent.bank_item_id` já resolvem o item
indiretamente e continuam exatamente como estão.

## 4. Plano de migration (quando autorizado)

Preserva 100% do dado existente sem trabalho manual — nenhum item fica
órfão em nenhuma etapa intermediária:

1. Cria a tabela `tesseract_brewstation_yeastbank_container`.
2. Cria 1 Container `"[Nome do Dispositivo] — Geral"` para cada
   `YeastStorageDevice` ativo hoje (`container_type="Outro"`).
3. Adiciona `container_id` em `bank_item`, **nullable** nesta etapa.
4. Backfill: para cada `YeastBankItem`, `container_id` = Container
   "Geral" do dispositivo que estava em `storage_device_id`.
5. Torna `bank_item.container_id` `NOT NULL`.
6. Remove `bank_item.storage_device_id`.

Cada passo é uma migration Alembic própria — nunca uma migration única
fazendo os 6 passos juntos, para permitir rollback intermediário se o
backfill do passo 4 encontrar inconsistência.

## 5. Navegação (fora do escopo de schema, registrado aqui pra não se perder)

Fluxo de drill-down combinado nesta mesma rodada de planejamento —
**tela integrada**, não CrudGen padrão, fase própria e futura (ver
seção 7):

```
Lista de containers → clique na linha → itens do container selecionado
  → clique no ícone da linha → detalhe do item (abas: starter · contagem · eventos)
```

Risco já conhecido do projeto (mesma lição da remoção do Designer v2,
BACKLOG Fase 12): interação de navegador complexa não é pega por teste
unitário — quando essa fase entrar, planejar teste em navegador
(Playwright ou equivalente) antes de escrever o JS, não depois.

## 6. Decisões descartadas / histórico do raciocínio

1. **Manter `storage_device_id` redundante em `YeastBankItem` além de
   `container_id`.** Descartado — duplicava o dado (dois lugares pra
   ficar desatualizado) só para economizar 1 join numa listagem;
   `container.device` resolve isso sem duplicação.
2. **Container virtual (`device_id` nullable).** Avaliado e descartado
   explicitamente — Container é sempre físico, sempre dentro de um
   Dispositivo.
3. **Container abranger múltiplos Dispositivos.** Descartado — não
   faz sentido físico (uma caixa não fica em duas geladeiras ao mesmo
   tempo); a FK é 1:N na direção Dispositivo → Container, nunca N:N.

## 7. O que fica para depois (fora desta skill)

- Implementação do model/migration/CrudGen desta proposta (aguarda
  autorização — "pode proceguir").
- Tela integrada de navegação (seção 5) — fase própria, só depois do
  schema aplicado e usado por um tempo.
- Se `feature_yeast_bank` continua abrigando Container/Item ou se vira
  Feature própria — não decidido, não é bloqueante para o schema acima.
- Campo `status`/capacidade em `YeastContainer` (ex.: "cheio") — não
  pedido, não incluído; fica como ideia futura se o uso real mostrar
  necessidade.
