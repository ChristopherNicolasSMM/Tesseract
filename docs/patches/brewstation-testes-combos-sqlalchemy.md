# Correção de testes dos combos e avisos SQLAlchemy

Base: patch de seletores/layout aplicado (commit local `b66176a`, equivalente
ao `b3b7c53` informado pelo usuário). Sem migration.

## Diagnóstico

Execução informada pelo usuário: **2 failed, 427 passed, 627 warnings**.
As duas falhas estavam em expectativas antigas do HTML inicial: nomes dos
layouts não selecionados eram procurados no fragmento após a conversão para
combo pesquisável. O patch anterior deixou essas duas expectativas pendentes.

Os testes agora extraem a lista de IDs do combo renderizado e consultam
`/api/options/dashboard_layouts`, verificando:

- novo painel da planta disponível na busca e selecionável no fragmento;
- painel de outra planta e apagado fora das opções do workspace;
- tela cheia mantendo painéis de todas as plantas disponíveis na busca.

Os avisos apresentados são `LegacyAPIWarning`, por uso de `Query.get()`.
Atualizados os usos nos controllers/services MANUAIS de workspace, dashboard,
timeline, logger e precificação envolvidos, além dos testes correspondentes.
`core/auth.py` usa `db.session.get(User, ..., options=...)` com o mesmo
`joinedload` de roles/permissões condicionado a `RBAC_SESSION_EAGER_LOAD`.
Teste parametrizado cobre carga antecipada ligada/desligada, permissões,
usuário inexistente e ausência do aviso no carregamento.

Referência técnica: https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.get

Não houve alteração de código gerado ou filtros de soft-delete, permissões,
transações, estoque ou comportamento da UI. Esta é manutenção dos pontos
indicados pelo log, não uma migração global de todas as consultas do projeto.
Avisos de outros caminhos deverão ser avaliados pelos seus logs específicos.

## Aplicação e testes

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-testes-combos-sqlalchemy.patch
```

Primeiro, executar somente as duas regressões e a proteção do carregamento
RBAC; evita repetir a suíte inteira de aproximadamente 50 minutos antes de
conferir esses pontos:

```powershell
python -m pytest tests/test_plant_workspace.py::test_dashboard_workspace_seleciona_layout_sem_sair_da_planta tests/test_plant_workspace.py::test_view_cheia_continua_mostrando_todos_os_layouts_do_sistema tests/test_phase2_rbac.py::test_user_loader_session_get_preserva_permissoes_e_config_eager -q -W error::sqlalchemy.exc.LegacyAPIWarning
```

Depois, regressão dos arquivos afetados e autenticação:

```powershell
python -m pytest tests/test_phase2_rbac.py tests/test_plant_workspace.py tests/test_dashboard_runtime.py tests/test_recipe_timeline.py tests/test_weak_ref_value_field.py tests/test_weak_ref_display_field.py tests/test_feature_brew_father.py tests/test_feature_envase.py tests/test_precificacao_envase.py -q
```

Verificados no ambiente de entrega: AST Python, diff e aplicação isolada do
format-patch com árvores idênticas. Pytest não executado neste ambiente,
pois faltam as dependências da aplicação e pytest.

## Roteiro visual

- `/brewstation/plant-workspace/<ID_PLANTA>?tab=dashboard`: criar painel,
  pesquisar pelo nome, selecioná-lo e confirmar que fica na mesma planta.
- `/brewstation/dashboards/<ID_LAYOUT>/view`: pesquisar painel de outra planta
  e abrir; disponibilidade geral da tela cheia preservada.
- Entrar/sair e abrir workspace com usuário administrador e operador limitado;
  conferir que ações e permissões continuam respeitadas.

## Continuidade

Não considerar a correção validada até os testes locais. As próximas etapas
funcionais (registro de envase/estorno e configurações avançadas) permanecem
pendentes. O roteiro visual do patch de seletores/layout continua aplicável.

## Correção da preparação do usuário de teste

Retorno local: os dois testes dos combos passaram; as duas variantes do
teste de user_loader falharam antes de chamar o loader por password_hash
obrigatório ausente. O usuário da fixture agora recebe senha por
User.set_password, como nos demais testes RBAC. Sem alteração de autenticação
ou schema. Patch incremental: brewstation-fixture-senha-rbac.patch.

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-fixture-senha-rbac.patch
python -m pytest tests/test_phase2_rbac.py::test_user_loader_session_get_preserva_permissoes_e_config_eager -q -W error::sqlalchemy.exc.LegacyAPIWarning
```

AST Python, diff e aplicação isolada verificados na entrega; pytest não
executado no ambiente de desenvolvimento. Validar as duas variantes localmente.
O manual de uso permanece válido; esta correção altera apenas a fixture.
