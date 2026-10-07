# Fase 3 — compatibilidade do ambiente de migrations

Implementado e verificado no ambiente de geração; aplicação e validação local
pendentes. Base: e9a23f6, após o pacote de unidades/conversões. A validação local do pacote de unidades/conversões permanece pendente. Não altera models, revisões, schema ou requirements.txt.
Não requer `flask db upgrade` para instalar esta correção.

## Levantamento e evidências

Os controllers manuais plant_workspace.py, dashboard_runtime.py e
recipe_timeline.py, além de core/auth.py, já usam Session.get. A correção antiga
está documentada em brewstation-testes-combos-sqlalchemy.md; não foi repetida.
A seleção de regressão desses fluxos é executada com LegacyAPIWarning como erro.

migrations/env.py ainda tentava db.get_engine() primeiro. O código instalado de
Flask-SQLAlchemy 3.1.1 declara a API obsoleta desde 3.0 e recomenda engine ou
engines[key]. requirements.txt fixa 3.1.1; a propriedade engine mantém o engine
padrão no contexto da aplicação. Removida a chamada e o fallback para versões
anteriores ao contrato atual. Não foi removido o tratamento de URL/metadados.

A seleção ampliada encontrou quatro Query.get na API manual Core de usuários
(detalhe, edição, desativação e ativação). Substituídos por Session.get mantendo
os mesmos decorators, respostas 404, validações e commits. Essa API não é
gerada pelo CrudGen. A falha afeta a conferência RBAC; não reabre os controllers
BrewStation já corrigidos.

A execução normal dos cinco arquivos de migrations passou: 15 passed in 13.21s.
Com PYTHONWARNINGS=error::DeprecationWarning, antes da correção:
**2 failed, 1 passed in 8.22s**, ambos em test_migrations_idempotent.py.
Erro reproduzido:

```text
DeprecationWarning: 'get_engine' is deprecated and will be removed in Flask-SQLAlchemy 3.2. Use 'engine' or 'engines[key]' instead. If you're using Flask-Migrate or Alembic, you'll need to update your 'env.py' file.
```

O helper de subprocesso dos testes agora adiciona um filtro específico para
esse aviso, preservando filtros recebidos. Evita que um retorno normal esconda
a regressão em stderr. Não transforma indiscriminadamente todos os avisos em
erro no funcionamento da aplicação.

## Contratos e limites

Os testes percorrem upgrade até o head único f8c214ab709e e downgrade em bancos
SQLite temporários. Cobrem schema criado pelos models, nomes históricos de
constraints/índices, referências, dados legados de tipo de produto, chave de
idempotência de envase e base de precificação. Nenhum downgrade foi executado
sobre banco instalado, e não é recomendado executá-lo como conferência local.
Não certificam PostgreSQL nem qualquer banco de produção particular.

Comparação do runtime com requirements.txt: Flask 3.1.3, Flask-SQLAlchemy 3.1.1,
SQLAlchemy 2.0.51, Flask-Migrate 4.1.0 e pytest 9.1.1 coincidem. Alembic instalado
é 1.20.0, enquanto o arquivo fixa 1.18.4; Werkzeug instalado é 3.1.9, fixado
3.1.8. Há outras diferenças transitivas e opcionais (inclusive ausência de
colorama, gunicorn e tzdata). Portanto esta execução não certifica um ambiente
recriado com todas as versões fixadas. Não houve instalação ou upgrade. Uma
reprodução completa do lock e matriz Windows/PostgreSQL fica pendente.
requirements.txt está em UTF-16; foi lido preservando o arquivo existente.

## Aplicação e testes

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-fase3-compatibilidade-migrations.patch
python -m pytest tests/test_migrations_idempotent.py tests/test_migration_schema_compat.py tests/test_migration_tipo_produto_legacy.py tests/test_migration_envase_request_key.py tests/test_migration_precificacao_basis.py -q --tb=short
python -m pytest tests/test_plant_workspace.py tests/test_dashboard_runtime.py tests/test_recipe_timeline.py tests/test_phase2_rbac.py -q -W error::sqlalchemy.exc.LegacyAPIWarning --tb=short
```

No ambiente de geração, comandos executados com `/usr/bin/python3` e
`PYTHONPATH=/workspace/scratch/af6b56a6223b/venv-yeast-audit/lib/python3.12/site-packages`.
A seleção final de migrations também usou PYTHONWARNINGS=error::DeprecationWarning.
Resultado: **15 passed in 11.73s** com depreciações como erro.
O teste com filtro específico também foi executado isoladamente sobre a base
anterior: **2 failed, 1 passed in 9.42s**, confirmando que o novo teste detecta
a chamada antiga sem depender do filtro global.

Não há alteração visual. Conferência opcional após reiniciar: abrir
`/brewstation/plant-workspace/<ID>?tab=dashboard`, alternar layout e conferir
sessão/receita existentes; abrir as abas Receita e Sessões. Para inspecionar o
banco instalado sem modificá-lo, executar `python -m flask db current` e
`python -m flask db heads`; comparar com o histórico real, sem usar stamp para
pular revisões. Só executar upgrade quando houver migrations pendentes reais.

## Sequência restante

| Item | Natureza / prioridade | Dependência | Migration | Conclusão |
| --- | --- | --- | --- | --- |
| Reproduzir dependências fixadas | Verificação proposta / próxima qualidade | Ambiente isolado com versões do arquivo, Windows e PostgreSQL disponíveis | Não | Instalação e suítes coerentes aprovadas nas versões fixadas |
| Moedas/câmbio | Desenho funcional / alta | Moeda-base, precisão, taxa/data/fonte e fronteira financeiro | Provável após desenho | Custo estrangeiro só entra após conversão explícita; histórico congelado |
| YeastBank físico | Desenho funcional / após estoque | Unidade física, genealogia, consumo, descarte/estorno | Provável | Eventos laboratoriais separados de movimentos físicos idempotentes |
| Recebimento parcial | Adiado | Quantidades restantes, estados e estornos | A determinar | Contrato e testes definidos antes de implementar |
| Hardware/PID | Levantamento proposto | Origem física e contrato de execução | A determinar | Software e ensaio físico registrados separadamente |


Resultado da seleção ampliada antes da correção da API de usuários:
**2 failed, 422 passed in 561.34s**. Falhas:
`test_soft_delete_deactivate_activate` e
`test_autodesativacao_invalida_a_propria_sessao`, ambas por LegacyAPIWarning
em api/routes/core/admin/users.py. A regressão após essa alteração é restrita
a tests/test_phase2_rbac.py; os outros três arquivos passaram e permaneceram
inalterados.


Na primeira repetição RBAC após corrigir a API: **1 failed, 11 passed in
14.75s**. O aviso restante vinha das duas leituras User.query.get do próprio
teste. Essas leituras foram atualizadas. Acrescentados cinco casos de contrato:
404 nas quatro operações por ID; detalhe, validação 422 e persistência da edição.

Resultado final RBAC/API: **17 passed in 20.30s**, com LegacyAPIWarning como
erro. Resultado consolidado: **444 casos distintos aprovados**, compostos por
412 do workspace/dashboard/timeline na seleção inicial, 17 RBAC/API na
repetição final e 15 de migrations. Os 10 casos RBAC que já haviam passado na
primeira seleção estão dentro dos 17 e não foram contados duas vezes.
`git diff --check` aprovado. Aplicação isolada na base e9a23f6, igualdade das
árvores e verificação reversa devem ser concluídas antes da entrega do patch.
