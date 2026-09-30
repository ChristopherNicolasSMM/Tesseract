# Histórico de sessões no workspace

A aba Sessões deixa de limitar o acesso aos 20 itens mais recentes.
Sessões, registros e alarmes têm paginação independente de 20 itens por
página, com Anterior/Próxima sem sair do workspace. A lista de sessões
permite busca por nome e filtro pelo status, usando `form-select` padrão.
Os status da sessão aparecem em português.

A seleção explícita de `session_id` consulta a sessão na planta, mesmo
quando ela não está na primeira página. Sessões apagadas, de outra planta
ou identificadores inválidos retornam erro 404, sem selecionar silenciosamente
outra sessão. A busca trata `%` e `_` como caracteres literais. Ao filtrar
ou trocar a página da lista, a seleção e as páginas dos eventos são reiniciadas.
Ao paginar registros/alarmes, a sessão e a página do outro histórico são
preservadas. A ordenação dos eventos usa data e ID para desempatar.

O resumo mostra volume real, início, conclusão e notas. Cada etapa abre
detalhes locais de duração, rampa, PID, disparo de alerta, notas e adições.
Os registros abrem origem, etapa e dados detalhados; os alarmes mostram tipo
e dados de reconhecimento. A leitura não altera estados, timers, alarmes,
estoque ou ledger. O Dashboard da planta permanece como acesso à execução.

Cadastro avançado da sessão permanece disponível. Este patch não oculta
novos menus e não substitui manutenção avançada nem reconhecimento de alarmes.
Não há migration. Não foram alterados services/controllers gerados pelo CrudGen.

URL principal para testar (substituir o ID):
`http://localhost:5000/brewstation/plant-workspace/<ID_PLANTA>?tab=sessions`

No fragmento, os parâmetros são `q`, `status`, `page`, `session_id`,
`logs_page` e `alarms_page`. Exemplos de teste: procurar uma sessão antiga,
alternar status, abrir detalhes de etapas e avançar os históricos de registros
e alarmes separadamente. Com mais de 20 itens, conferir que todos são acessíveis.

```shell
pytest tests/test_plant_workspace.py tests/test_weak_ref_value_field.py
```

Validação neste ambiente: sintaxe Python/JavaScript e aplicação do patch.
Pytest e revisão visual devem rodar no ambiente do projeto.
