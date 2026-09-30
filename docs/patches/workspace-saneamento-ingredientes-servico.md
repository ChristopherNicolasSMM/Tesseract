# Saneamento de ingredientes — 1A: serviço local

Primeiro incremento funcional do plano de continuidade. Ainda não adiciona
rota ou interface de edição. Não há migration, `db upgrade` ou mudança de menus.

O serviço manual `ingredient_sanitation_service.sanear_ingrediente()` recebe
receita/ingrediente e apenas `status_resolucao`/`material_id`. Identificadores
devem ser inteiros positivos, sem booleanos. Confere receita/linha não apagadas
e pertencimento da linha à receita. A receita é global, não exclusiva da planta.

`resolvido` exige material existente, não apagado e ativo, consultado pelo
ponto público `material_lookup.get_material()`. `ignorado` exige vínculo
vazio e remove o material da linha. Outras decisões são rejeitadas.

A operação bloqueia receitas referenciadas por qualquer sessão, inclusive
rascunhos, sessões ainda não confirmadas e sessões na lixeira. Isso evita
mudar o consumo futuro e a conferência histórica pelo novo caminho local.
A futura revisão completa ainda precisa preservar todos os dados da receita.

O serviço altera apenas vínculo/status da linha. Mantém quantidade/unidade,
especificações, origem, outras linhas e receitas, o de-para global, os lotes,
seus custos e o estoque. Não cria material nem atualiza `IngredientMapping`.
Repetir a decisão produz o mesmo estado; não há log/baixa novo nessa ação.
Vincular um material não corrige automaticamente unidade ou quantidade:
essas pendências permanecem na conferência existente.

Por padrão confirma a transação. `commit=False` faz flush e permite uma
operação composta controlar o commit. Falha faz rollback da tentativa.
Controllers futuros deverão verificar login/RBAC/contexto de planta antes
de chamar o serviço; 1A não expõe operação HTTP nem cria permissão nova.

## Limites e continuidade

O serviço será conectado à aba Receita no incremento 1B. Não substitui
`confirmar_mapeamento()` global, importadores ou hooks do CRUD; não oferece
proteção geral desses caminhos antigos. A preparação de revisão completa e
a edição de quantidade/unidade ficam no 1C. Não presume isolamento contra
alterações concorrentes feitas por outros caminhos do sistema.

Neste patch, não há URL nova nem comportamento visual alterado. Para conferir
a regressão visual atual, abrir:

`http://localhost:5000/brewstation/plant-workspace/<ID_PLANTA>?tab=recipe`

Selecionar a receita e verificar conferência/custo/timeline e links existentes.
O botão de saneamento local ainda não deve aparecer.

## Verificação

Testes adicionados à suíte existente cobrem escopo, lixeira, sessões em todos
os estados, material indisponível, decisão incoerente, preservação dos campos,
ausência de efeitos no estoque/de-para, repetição, conversão ainda pendente,
rollback de falha no commit e composição com rollback do chamador.

```shell
python -m pytest tests/test_mash_control_ingredient_resolution.py
python -m pytest tests/test_plant_workspace.py tests/test_feature_brew_father.py tests/test_feature_envase.py tests/test_addon_estoque.py
```

Sintaxe Python, diff e aplicação com `git am --keep-cr` foram verificados.
Pytest não foi executado: o ambiente não tem as dependências e a tentativa
de instalar pytest não encontrou distribuição disponível. Testes locais
continuam necessários; não há resultado aprovado de pytest neste incremento.
