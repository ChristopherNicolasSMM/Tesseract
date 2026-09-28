# 03 — Funcionalidades (Integração BrewFather)

## Sincronizar Receitas

Busca as receitas da sua conta BrewFather e traz pro sistema —
ingredientes, etapas de mostura e fermentação. Pode ser clicado várias
vezes; receitas já importadas não são duplicadas.

## Selecionar Receitas pra Sincronizar

Alternativa ao "Sincronizar Tudo": mostra a lista de receitas
disponíveis na sua conta BrewFather (nome, estilo, tipo) com um selo
de status em cada uma —

- **Nova**: nunca foi importada.
- **Já importada**: já existe no sistema.
- **Apagada — pendente de reimportar**: já existiu, foi apagada, e uma
  nova sincronização vai trazê-la de volta como uma nova versão.

Filtre por pasta (incluindo suas subpastas) ou tag, além de nome, estilo,
tipo e situação. As pastas e tags são lidas do Brewfather e filtradas
no portal; caso haja mais de 500 receitas, os filtros abrangem apenas
as receitas carregadas. Escolha a ação e marque até 50 receitas:

- **Sincronizar novas** importa as receitas ainda não presentes.
- **Ressincronizar importadas** busca novamente o detalhe e cria outra
  versão no BrewStation. Lotes existentes continuam ligados à versão anterior.
- **Mover importadas para lixeira** oculta as receitas locais escolhidas;
  não exclui os lotes nem altera a conta Brewfather.

Os botões de ações gerais operam sobre **todas as receitas importadas**
no Tesseract, mesmo fora da página exibida. A ressincronização geral
aceita até 500 receitas por operação por causa do limite da API; para
volumes maiores, selecione grupos menores. A remoção geral usa a
lixeira, portanto é reversível pelo fluxo de restauração de receitas.

## Conferir inventário com o Estoque

Nas abas **Fermentáveis** e **Lúpulos**, use **Vincular** para escolher
um Material do Tesseract. O de-para de receitas pode sugerir um Material
com nome igual, mas a escolha precisa ser confirmada. O portal mostra
o saldo local, o saldo no Brewfather e a diferença, após conversão de
kg e g. Material sem unidade base, sem saldo ou com unidade incompatível
mostra o motivo do bloqueio. Materiais pendentes de revisão também são
sinalizados. Nesta etapa, nenhum dado é enviado e nenhum saldo é alterado.

O vínculo é persistente por ID do item Brewfather. É preciso rodar
`flask db upgrade` após aplicar o patch para criar a tabela correspondente.

## Sincronizações (histórico)

Lista de cada sincronização já feita — quando rodou, quantas receitas
processou, e se deu algum erro. O campo Tipo é uma lista de opções
fixas, conforme as anotações do CrudGen; atualmente só receitas são
importadas, enquanto lotes e inventário permanecem para consulta.

## Resolver Ingredientes Pendentes (De-Para)

Tela que aparece quando existem ingredientes importados que ainda não
foram ligados a um Material do Estoque. Duas formas de resolver cada
um:
- **Buscar Material existente**: digite o nome no campo de busca e
  escolha na lista.
- **Cadastrar Material novo**: digite um nome novo — o sistema cria o
  Material automaticamente (com dados básicos, que podem ser
  completados depois na tela de Materiais).

## Cadastrar todos automaticamente

Atalho pra quem não quer resolver ingrediente por ingrediente —
cadastra um Material novo pra cada ingrediente ainda pendente, de uma
vez só. Os materiais criados assim ficam marcados como "pendente de
revisão" no Estoque (ver manual do Estoque).
