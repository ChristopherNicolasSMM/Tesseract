# Mapeamento: exemplos NiceAdmin → tipos de componente do Designer

Levantamento feito em cima dos 32 arquivos reais de
`static/modelo_paginas_nice_admin/`. Cada exemplo do template vira, na
minha proposta, **ou** um tipo de componente novo **ou** uma variação
de propriedade de um componente já existente (pra não multiplicar
tipo sem necessidade) **ou** não vira componente nenhum (é recurso de
página inteira, ou infraestrutura que já existe em outro lugar do
Tesseract).

## Tier 1 — essencial pra substituir uma tela CrudGen (esta leva)

| Exemplo NiceAdmin | Componente proposto | Observação |
|---|---|---|
| `forms-elements.html` (Text/Email/Password/Number/Date/Time/Textarea) | Variação de propriedade do `textbox` já existente (`input_type`) | Não é tipo novo — só estende `_DEFAULT_PROPERTIES["textbox"]` |
| `forms-elements.html` (Select, Multi Select) | **`select`** (novo) | Bind a opções estáticas OU a uma Ação de Dado (substitui o que hoje só existe via `/api/options` de weak-ref dentro do CrudGen) |
| `forms-elements.html` (Checkboxes, Switches) | **`checkbox`** (novo) | "Switch" é variação visual (`style: switch`), mesmo componente |
| `forms-elements.html` (Radios) | **`radio`** (novo) | Grupo de opções exclusivas |
| `forms-validation.html` (as 3 variações) | Nenhum componente novo | Já resolvido pelo motor de Validação (Fase 7b) que o `textbox` já consome via `rules` |
| `forms-layouts.html` (Horizontal/Vertical/Multi-coluna/Floating labels) | Propriedade (`label_position`) do `textbox`/`select`/etc | Canvas já é livre (x/y) — "layout" aqui é só onde o label fica relativo ao campo |
| — (não tem exemplo direto no NiceAdmin, é conceito do DEVStationFlask original) | **`form_container`** (novo) | Agrupa campos ligados ao MESMO registro — todo filho herda o binding do container. É o que fecha "editar um registro" |
| `tables-data.html` (Datatables) | **`datagrid`** (novo) | Usa `simple-datatables` já vendorizado + já inicializado pelo `main.js` que corrigimos — motor client-side pronto, só falta gerar `<table class="datatable">` com as linhas vindas da Ação de Dado |
| `tables-general.html` (Dark/Striped/Bordered/Hoverable/Small) | Propriedade (`table_style`) do `datagrid` | Variações visuais de Bootstrap, não tipo novo |

## Tier 2 — barato de incluir (reaproveita CSS/lib já vendorizada, zero engenharia nova de bind)

| Exemplo NiceAdmin | Componente proposto | Observação |
|---|---|---|
| `components-cards.html` (8 variações) | **`card`** (novo) | Header/footer/imagem viram propriedades, não tipos separados |
| `components-alerts.html` | **`alert`** (novo) | Pode ser alvo de regra de Visibilidade (Fase 7b, grupo ainda sem engine) |
| `components-badges.html` | **`badge`** (novo) | Componente pequeno, útil em `datagrid`/`card` também (célula tipo badge) |
| `components-progress.html` | **`progress_bar`** (novo) | É literalmente o que a regra "Controlar ProgressBar" (catálogo de Cálculo, Fase 7b) já espera ter como alvo — fecha outro gap antigo |
| `components-list-group.html` | **`list`** (novo) | Como `datagrid`, mas pra lista simples (sem colunas) — bind a Ação de Dado |

## Tier 3 — maior complexidade ou menor prioridade pro objetivo "substituir CRUD" (proponho depois)

| Exemplo NiceAdmin | Componente proposto | Observação |
|---|---|---|
| `components-tabs.html` | **`tabs`** (novo, container) | `users-profile.html` mostra o caso de uso real: Overview/Editar/Configurações/Senha em abas — útil, mas é container complexo |
| `components-accordion.html` | **`accordion`** (novo, container) | Mesma família de `tabs` |
| `components-modal.html` | Não vira componente de canvas | Melhor reaproveitar o sistema de modal **já padronizado** (skill 15, `core_confirm_dialog.js`/`core_popups.css`) via uma **Ação** (`open_modal`), em vez de duplicar outro motor de modal |
| `components-carousel.html` | **`carousel`** (novo) | Baixa prioridade, sem relação com substituir tela CRUD |
| `components-pagination.html` | Não vira componente próprio | `simple-datatables` já resolve paginação dentro do `datagrid` |
| `components-breadcrumbs.html`, `components-tooltips.html` | Não viram componente | Breadcrumb é resolvido pela árvore de Transação (skill 10); tooltip vira propriedade (`tooltip_text`) de qualquer componente, não tipo próprio |
| `forms-editors.html` (Quill/TinyMCE) | **`rich_text`** (novo) | Ambas as libs já vendorizadas; maior esforço de wiring (toolbar, sanitização de HTML salvo) |
| `charts-apexcharts.html` / `charts-chartjs.html` / `charts-echarts.html` | **`chart`** (novo) | As 3 libs já estão vendorizadas só de terem vindo junto no template — proposta: escolher **uma só** como padrão do Designer (ApexCharts ou Chart.js), pra não carregar 3 engines de gráfico em toda página. Decisão sua quando chegarmos nesse tier. |

## Fora do catálogo de componentes — vira recurso do *editor*, não tipo de componente

| Exemplo NiceAdmin | Uso proposto |
|---|---|
| `pages-login.html`, `pages-register.html`, `pages-contact.html`, `pages-faq.html`, `pages-blank.html`, `pages-error-404.html` | Viram **templates de página prontos** — opção de "criar a partir de modelo" na tela `/admin/designer/`, em vez de começar sempre de canvas vazio. Não são tipo de componente, são ponto de partida composto. |
| `users-profile.html` | Referência de composição real (Tabs + `form_container` + `datagrid` de atividades) — bom caso de teste de ponta a ponta quando os componentes de Tier 1/2 estiverem prontos |
| `icons-bootstrap.html`, `icons-boxicons.html`, `icons-remix.html` | Não são componente — viram o **seletor de ícone** dentro do editor (qualquer componente com propriedade de ícone abre essa galeria) |
