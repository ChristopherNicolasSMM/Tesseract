# Dashboards dentro do workspace da planta

A aba Dashboard permite selecionar os layouts da própria planta pelo
`form-select` padrão, sem abrir outra página. A seleção usa o parâmetro
`layout_id` do fragmento e rejeita layouts de outra planta, apagados ou
identificadores inválidos. Sem seleção explícita, mantém a escolha do painel
padrão ou do primeiro disponível.

O botão Configurar layouts abre um card expansível dentro da aba. Nele é
possível editar nome, descrição e dimensões do painel selecionado e criar
painéis adicionais. A criação preserva o comportamento existente: apenas o
primeiro painel é automaticamente marcado como padrão. Depois de criar um
painel adicional, selecione-o no combo para configurá-lo.

A edição exige `dashboard_layouts.update`, verifica o pertencimento à planta,
aceita apenas dimensões inteiras positivas e mantém os demais campos e
widgets. Usa o service existente, sem alterar código gerado pelo CrudGen.
A criação continua exigindo `dashboard_layouts.create`.

O atalho Importar Receita para Brassar abre a aba Receita do workspace.
Na tela completa de dashboard, os atalhos e seletor mantêm seu comportamento.
O Modo Edição existente continua responsável pelos widgets e tubulação;
a tabela de widgets permanece como acesso avançado.

Não há migration nem ocultação adicional de menus neste patch. A edição
avançada de fundo, standby e painel padrão permanece no CRUD de layouts.
Exclusão/restauração e configuração avançada continuam para etapas posteriores.

Validação local: sintaxe Python, scripts novos e aplicação do patch. A suíte
pytest deve ser executada no ambiente do projeto:

```shell
pytest tests/test_plant_workspace.py tests/test_weak_ref_value_field.py
```

Verificação visual: com dois painéis na mesma planta, alternar entre eles,
editar e salvar o segundo, criar um terceiro e selecioná-lo. Conferir que a
aba permanece no workspace e que o Modo Edição ainda carrega os widgets.
