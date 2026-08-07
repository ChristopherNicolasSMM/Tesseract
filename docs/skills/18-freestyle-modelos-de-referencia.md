# 18 — Modelos Freestyle: estrutura e convenção

> **Status: EXECUTADA (Fase 13).** Telas de referência **vivas** para
> quem vai escrever uma página customizada (`/admin/designer/`, skill
> 16/17) à mão — renderizadas dentro do layout real, com o tema ativo,
> testadas (`tests/test_freestyle_modelos.py`), ao contrário de um
> arquivo estático que só existe fora do sistema.
>
> Complementa a skill 17: aquela documenta o *fluxo de dado*; esta
> documenta a *estrutura de arquivo e a convenção de nome* que o
> freestyle introduziu, para quem for criar um modelo novo.

---

## 1. Onde cada peça mora

```
controller/core/freestyle_model.py     uma função por modelo, sem lógica de negócio
templates/core/freestyle/
├── index.html                         índice com os quatro cartões
├── model_minimal.html                 esqueleto mínimo
├── model_abas.html                    controle de abas
├── model_consumption.html             os três caminhos de dado
└── model_full.html                    galeria completa de componentes
static/js/freestyle/
├── freestyle-tesseract-data.js        helper compartilhado (ver skill 17, §8)
├── model_abas-tabs.js
├── model_consumption-telas.js
├── model_full-graficos.js
├── model_full-tabelas.js
├── model_full-formularios.js
└── model_full-interacoes.js
```

## 2. Achado real que define a regra 1

`templates/` **não é servível** — o Flask serve `static/`
(`static_folder`), não `template_folder`. Um `<script src="…/templates/
…">` retorna 404 sempre. Por isso todo JavaScript de uma tela
freestyle mora em `static/js/freestyle/`, nunca ao lado do `.html` em
`templates/core/freestyle/`, mesmo que pareça mais organizado manter
os dois juntos.

## 3. Convenção de nome do arquivo `.js`

| Padrão | Quando usar | Exemplo |
|---|---|---|
| `model_<nome>-<responsabilidade>.js` | JS específico de UM modelo | `model_full-graficos.js` |
| `freestyle-<responsabilidade>.js` | Compartilhado por mais de um modelo | `freestyle-tesseract-data.js` |

Um modelo com várias responsabilidades vira **vários arquivos**, um por
responsabilidade (`model_full-graficos.js`, `-tabelas.js`,
`-formularios.js`, `-interacoes.js`) — nunca um `model_full.js` só,
que viraria um arquivo enorme e sem fronteira clara do que cada trecho
faz. Cada `.html` inclui os `.js` que precisa via `{% block extra_js
%}`, na ordem de dependência (o helper compartilhado sempre primeiro).

## 4. Regra de conteúdo do template

O `.html` é **só estrutura** — nenhum `<script>` inline além dos
`<script src="…">` do `extra_js`. Toda lógica (inicializar lib,
buscar dado, tratar evento) vive no `.js` correspondente. Isso é
verificado por teste (`test_full_nao_tem_javascript_inline`) — não é
só estilo, quebra o build se for violado.

## 5. Bibliotecas: só inclua o que a tela usa

O layout (`core/base.html`) já carrega Bootstrap, Bootstrap Icons,
Boxicons, ApexCharts e Simple DataTables. ECharts, Chart.js, Quill,
Remixicon e TinyMCE existem em `static/vendor/` mas **não** são
carregados por padrão — cada um é peso extra em toda visita ao
sistema, mesmo em telas que não usam gráfico ou editor de texto.
Inclua no `extra_css`/`extra_js` só da página que precisar
(`model_full.html` é o exemplo — carrega ECharts e Quill porque os
usa; os demais modelos não).

## 6. Passar variável do controller para o template

Duas formas, com finalidades diferentes (exemplo real em
`freestyle_model.consumption`):

1. **Direto no HTML** — quando o valor é conteúdo visível
   (`<input value="{{ q }}">`).
2. **Bloco JSON** — quando o valor é configuração para o JavaScript
   (`<script type="application/json" id="freestyle-config">{{ config
   | tojson }}</script>`, lido via `TesseractData.config()`). Evita
   montar JavaScript por concatenação de string no Jinja, que quebra
   com aspas/acento vindos do servidor e é vetor de XSS.

**Nunca** passe segredo (chave de API, senha de conexão) por nenhuma
das duas formas — tudo que chega ao template chega ao navegador. Dado
que exige credencial vai por Ação de Dado (skill 17).

## 7. Como criar um modelo novo

1. Função nova em `controller/core/freestyle_model.py`, seguindo o
   padrão das existentes (`@login_required`, docstring explicando o
   que a tela demonstra).
2. Template em `templates/core/freestyle/model_<nome>.html`,
   `extends "core/base.html"`, com o cabeçalho de comentário Jinja
   (`{#- … -#}`) explicando o propósito — ver `model_minimal.html`
   para o mínimo, `model_full.html` para o padrão de seções longas
   com índice interno.
3. JS em `static/js/freestyle/model_<nome>-<responsabilidade>.js`,
   seguindo a convenção da seção 3.
4. Cartão novo em `templates/core/freestyle/index.html`.
5. Teste em `tests/test_freestyle_modelos.py` — no mínimo: exige
   login, renderiza 200, e (se tiver JS) o script é servido e
   referenciado.

## 8. Pendência registrada

`static/modelo_paginas_nice_admin/_modelo-pagina-{basico,completo}.html`
(Fase 12) cobrem terreno parecido com `/freestyle/consumption` e
`/freestyle/full`, mas como arquivo estático — sem teste, sem tema
aplicado ao abrir direto pelo navegador. Decisão de consolidar num só
caminho, ou manter os dois, ainda em aberto — ver BACKLOG.md, Fase 13.
