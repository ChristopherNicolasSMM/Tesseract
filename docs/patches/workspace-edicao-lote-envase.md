# Edição básica e continuidade do lote no workspace

A aba Sessões ganha o card expansível Editar dados do lote, disponível
com `brew_sessions.update`. O formulário edita apenas nome, notas e volume
real em litros, por meio do `BrewSessionService` existente. Não modifica
status, planta, receita, etapa atual, timers, confirmação de ingredientes
ou custo registrado, mesmo se esses campos forem enviados manualmente.

O volume aceita zero, números não negativos finitos e valor em branco
(não medido), seguindo a regra do model. A rota aceita vírgula decimal.
Nome vazio ou acima de 100 caracteres e volume negativo/NaN/infinito são
rejeitados. A sessão e a planta precisam existir e estar fora da lixeira.
Ao salvar via AJAX, permanece a seleção e a paginação atual do histórico.

O card Ingredientes e custo do lote reaproveita os serviços de conferência
e estimativa antes da confirmação, sem movimentar estoque. Exibe os itens,
as pendências e identifica estimativas incompletas. Após confirmar insumos,
mostra apenas o custo registrado da sessão, sem recalcular o custo histórico.
O acesso à receita mantém o workspace; o atalho para confirmar ingredientes
abre a tela existente do lote, com sua regra de confirmação e baixa.

Com `envases.list`, aparece o card Envase e precificação com todos os
envases não apagados daquele lote, incluindo os cancelados para rastreabilidade.
Links para o detalhe exigem `envases.detail`. O atalho para simular abre
`/brewstation/precificacao-envase/?lote_id=<ID_SESSAO>` com o combo padrão
preenchido. Lote inválido ou apagado retorna 404. Sem parâmetro, o fluxo
de escolha de lote permanece disponível. Abrir essa página não calcula,
salva ou confirma automaticamente.

O retorno da precificação usa o workspace com `tab=sessions&session_id=...`.
A casca passa a respeitar essa seleção inicial, permitindo voltar também
a sessões antigas. Alterações do volume influenciam simulações futuras;
custos e componentes já registrados nos envases não são alterados.

Não há migration, alteração do ledger ou novos menus. Os arquivos gerados
pelo CrudGen não foram editados.

## Validação

URL principal (substituir os IDs):
`http://localhost:5000/brewstation/plant-workspace/<ID_PLANTA>?tab=sessions&session_id=<ID_SESSAO>`

Editar nome, notas e volume; salvar; abrir a precificação pelo card; verificar
o lote preenchido e voltar à mesma sessão. Conferir uma sessão ainda não
confirmada e outra com custo registrado. Verificar que os envases apresentados
pertencem ao lote selecionado.

```shell
pytest tests/test_plant_workspace.py tests/test_weak_ref_value_field.py tests/test_feature_envase.py
```

Validação neste ambiente: sintaxe Python/JavaScript e aplicação do patch.
A suíte pytest e a revisão visual precisam rodar no ambiente do projeto.
