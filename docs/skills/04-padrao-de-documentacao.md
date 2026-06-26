# 04 — Padrão de Documentação (Técnica + Manual)

Toda documentação do Tesseract — Core, Addon, Feature ou Plugin — segue
**dois trilhos obrigatórios e separados**, nunca misturados no mesmo
arquivo:

1. **Documentação Técnica** — para quem vai manter, criar ou expandir o
   sistema (dev humano ou IA).
2. **Manual** — para quem vai usar o sistema no dia a dia (usuário final,
   ex.: você operando a cervejaria).

## Onde cada documento vive

```
docs/
├── technical/
│   ├── 01-visao-geral.md
│   ├── 02-diagrama-c4.md
│   ├── 03-fluxos.md
│   ├── 04-modelo-de-dados.md
│   ├── 05-casos-de-uso.md
│   └── 06-manutencao-e-expansao.md
└── manual/
    ├── 01-introducao.md
    ├── 02-primeiros-passos.md
    ├── 03-funcionalidades.md
    └── 04-perguntas-frequentes.md
```

Essa estrutura se repete em **três escalas**:

| Escala | Onde |
|---|---|
| Sistema inteiro | `docs/` na raiz do Tesseract |
| Por Addon | `addons/addon_[nome]/docs/` |
| Por Feature | `addons/addon_[nome]/features/feature_[nome]/docs/` |

Plugin segue o mesmo padrão (`plugins/plugin_[nome]/docs/`), mas pode
dispensar `04-modelo-de-dados.md` (não tem tabela) e `02-diagrama-c4.md`
costuma ficar reduzido a um diagrama de contexto simples.

---

## Trilho 1 — Documentação Técnica

### 01-visao-geral.md
Propósito do módulo em poucos parágrafos, suas dependências (`requires` do
manifesto), o que ele expõe (`provides`), e um link para os demais
documentos técnicos.

### 02-diagrama-c4.md
Os 4 níveis do modelo C4, usando **Mermaid** (`C4Context`, `C4Container`,
`C4Component`, `C4Dynamic` quando aplicável):

| Nível | Escopo no Tesseract |
|---|---|
| Contexto | Sistema Tesseract + atores externos (usuário, BrewFather API, MQTT broker, Telegram) |
| Container | Core, cada Addon ativo, cada Plugin ativo, banco de dados, broker MQTT |
| Componente | Dentro de **um** Addon/Feature: `ModuleManager`, services, controllers daquele módulo |
| Código (opcional) | Só quando a complexidade interna de uma classe específica justificar — não é padrão obrigatório |

No nível Sistema (`docs/technical/`), gera-se Contexto + Container. No nível
Addon/Feature, gera-se Componente (o Container já foi coberto na escala
acima).

### 03-fluxos.md
Diagramas de fluxo (**Mermaid `flowchart`** para lógica condicional,
**Mermaid `sequenceDiagram`** para interação entre módulos/serviços/usuário
ao longo do tempo). Mínimo obrigatório por módulo:

- 1 fluxo do "caminho feliz" da operação principal do módulo
- 1 sequência mostrando a interação com o `EventBus`/`ModuleManager`, se houver

### 04-modelo-de-dados.md
Diagrama **ER/MER** em Mermaid (`erDiagram`), cobrindo as tabelas daquele
módulo (já com nome completo prefixado, conforme skill 02) e as FKs
permitidas (nunca cross-addon, conforme a mesma skill). Inclui uma tabela
textual logo abaixo do diagrama com: nome da tabela, descrição de negócio
de cada coluna não óbvia, e regra de soft-delete se aplicável.

### 05-casos-de-uso.md
Diagrama de **caso de uso** em Mermaid (sintaxe `flowchart` adaptada com
nós de ator e elipses de caso, já que Mermaid não tem um tipo nativo de UML
use-case — alternativa: descrição textual estruturada por ator quando o
diagrama não acrescentar clareza). Cada caso de uso lista: ator, pré-condição,
fluxo principal, fluxos alternativos, permissão RBAC exigida (`<plural>.<acao>`).

### 06-manutencao-e-expansao.md
A seção mais prática para uso futuro (por você ou por uma IA):

- Como adicionar um campo a um model existente (e quais arquivos o CrudGen
  toca vs. quais hooks preservam customização — ver skill 00, termo Hook).
- Como adicionar uma nova Feature a um Addon existente (checklist: manifesto,
  prefixo de tabela, i18n, registro no `ModuleManager`).
- Como depreciar/remover uma Feature ou Addon sem deixar tabela órfã (ordem
  de migrations, o que fazer com FKs internas do próprio módulo).
- Pontos de extensão conhecidos (onde o módulo expõe eventos via `EventBus`
  para outros módulos reagirem, sem acoplamento direto).

### Exceção de escopo: `07-catalogo-de-transacoes.md` (só nível Sistema)

`docs/technical/07-catalogo-de-transacoes.md` existe **só na escala
Sistema**, não em Addon/Feature/Plugin — não faz sentido por módulo,
já que o catálogo de Transações é global. É **gerado
automaticamente** (`python run.py transactions-doc`), não escrito à
mão como os demais — qualquer edição manual se perde na próxima
geração.

---

## Trilho 2 — Manual (usuário final)

Tom de escrita: direto, sem jargão técnico, sempre em PT-BR (texto do
manual em si não passa pelo sistema de i18n de chave/tradução da skill 00 —
é prosa livre, não label de UI). Print de tela é bem-vindo quando houver
UI; se ainda não houver, descrever o fluxo em passos numerados.

### 01-introducao.md
O que o módulo faz, em uma linguagem de "para que serve isso na prática" —
sem mencionar Addon/Feature/Plugin ou qualquer termo de arquitetura.

### 02-primeiros-passos.md
Passo a passo de configuração inicial (ativar o módulo, preencher
parâmetros obrigatórios, primeira tela que o usuário vai ver).

### 03-funcionalidades.md
Uma seção por funcionalidade visível, organizada como o usuário navega no
menu — não como o código está organizado.

### 04-perguntas-frequentes.md
Cresce ao longo do uso real; começa vazio ou com 2-3 perguntas previstas e
é atualizado conforme dúvidas reais aparecerem.

---

## Regra de ouro desta skill

> Documentação Técnica nunca tenta ser amigável para usuário final, e
> Manual nunca expõe nome de tabela, classe ou diagrama C4. Se um diagrama
> ER aparecer dentro de `docs/manual/`, ele foi colocado no lugar errado —
> mover para `docs/technical/04-modelo-de-dados.md`.

## Quando esta skill é aplicada

- Todo Addon/Feature/Plugin novo nasce com os dois trilhos de `docs/`
  criados (mesmo que alguns arquivos comecem como esqueleto a preencher).
- Checklist de validação de manifesto (skill 03) ganha o item: `docs/technical/`
  e `docs/manual/` presentes com pelo menos `01-*.md` preenchido em cada um.
