# Fase 3 — versões explícitas de política monetária

Base: conteúdo `8bde9a5` (câmbio), cuja aplicação/validação o usuário confirmou
em 08/10/2026. Hash local após git am pode diferir; comparar conteúdo.

## Entrega

- Versões append-only de casas decimais e arredondamento, com data, motivo e autor.
- Política inicial reconhecida como v1 sem mudança de ID, DTO ou tabela original.
- Seleção explícita de revisão em simulação/confirmação e quantização pública.
- Snapshot com identidade/validade da revisão; histórico anterior preservado.
- Concorrência por expected_version + unique composta, sem sobrescrita silenciosa.
- Tela/API/lista/pesquisa/paginação e menu automático no padrão AddonBase.
- Migration `e15a2b76d340`, parent `d04f1a65c239`, criando só tabela de revisões.

Nova revisão não é escolhida automaticamente nem usada para recalcular operações
confirmadas. Política inicial continua usada por payload/API/serviço antigos.
Moeda-base não é alterada: mudança exige tratar saldos/contexto organizacional.
Precisão e arredondamento são os aspectos versionados neste pacote.

## Aplicação em PowerShell

Pare a aplicação e confira `git status` sem alterações pendentes. No ambiente
que já recebeu o patch de câmbio validado:

```powershell
git -c gc.auto=0 am --keep-cr .\tesseract-fase3-financeiro-versoes-politicas.patch
python run.py db upgrade
python -m pytest tests/test_financeiro_policy_versions.py tests/test_financeiro_exchange.py tests/test_financeiro_foundation.py tests/test_financeiro_ui_integrity.py tests/test_migrations_idempotent.py tests/test_migration_schema_compat.py -q
```

Reinicie e atualize com Ctrl+F5. Não há dependência nova no requirements.
Downgrade é bloqueado se houver qualquer revisão; não usar como estorno.

## Conferência local

1. `/financeiro/policy-versions/`: escolha organização com política inicial
   HALF_UP/2 casas. Cadastre revisão HALF_EVEN/2 casas, data e motivo.
2. Nova revisão recebe número 2 e ID próprio; confira moeda-base/autor/histórico.
   Não permite mudança de base, edição ou exclusão.
3. `/financeiro/conversions/`: moeda original igual à base, valor 1.005, taxa
   vazia, data igual ou posterior à revisão. Simule com política inicial: 1.01;
   depois selecione revisão 2: 1.00. Simulação não aumenta histórico.
4. Confirme nova operação com referência/chave próprias e confira versão/motivo
   em Detalhes do cálculo. Uma operação anterior mantém o valor/política originais.
5. Revise data anterior ou versão de outra organização: erro com campos mantidos.
6. Em duas abas, abra formulário na mesma última versão; salve uma revisão na
   primeira e tente salvar outra na segunda. Segunda deve dar conflito 409,
   preservando entrada. Recarregue e confira antes de repetir deliberadamente.
7. Confira temas claro/escuro e largura móvel; leitor de lista não vê cadastro.

[Manual](../../addons/addon_financeiro/docs/manual/03-versoes-monetarias.md) e
[contratos](../../addons/addon_financeiro/docs/technical/03-versoes-monetarias.md).

## Estado e sequência

Câmbio anterior aplicado/validado pelo usuário. Este pacote aguarda aplicação
local. Próxima frente: contexto organizacional de compras/estoque, começando
pela definição de propriedade dos materiais/saldos e tratamento explícito do
legado global. Depois moeda em cotação/pedido, recebimento convertido e títulos/
contas/liquidações. Não atribuir organização/moeda ao legado nem alterar custos
sem decisão de escopo e migração verificável. Mudança de base depende desse desenho.

## Evidências de testes

Runtime de teste novo em scratch; Python 3.12, todas as versões fixadas no
requirements reproduzidas, inclusive Alembic 1.18.4. `pip check`: sem conflitos.
Não alterado requirements nem instalado componente no ambiente do usuário.

Comando prefixado por `/workspace/scratch/d853491ba74a/venv-policy/bin/python`:

- `-m pytest tests/test_financeiro_policy_versions.py -q --tb=short --show-capture=no -W error::sqlalchemy.exc.LegacyAPIWarning`:
  10 passed e 1 failed in 18.14s. Falha real na tela: serviço list_organizations
  retorna objetos ORM, acesso incorreto como dict. Corrigido para o contrato existente.
- Reexecução de `test_ui_api_menu_search_and_form_preservation`: 1 passed in 2.88s.
- `-m pytest tests/test_financeiro_foundation.py tests/test_financeiro_exchange.py tests/test_financeiro_ui_integrity.py tests/test_migrations_idempotent.py tests/test_migration_schema_compat.py -q --tb=short --show-capture=no -W error::sqlalchemy.exc.LegacyAPIWarning`:
  144 passed in 145.94s. Inclui upgrade real do zero após create_all e downgrade
  completo vazio, campos/menus legados, Decimal e idempotência do câmbio.

Teste novo de concorrência usa violação UNIQUE real após simular leitura antiga;
não é certificação de stress multiworker/PostgreSQL. Rollback, inativação,
imutabilidade, pertencimento e limites temporais cobertos por testes funcionais.

O teste Chromium existente foi ampliado para versões; verificação sintática Node
aprovada, mas execução visual não concluída: navegador anterior indisponível
após renovação do runtime; download do novo navegador não devolveu ZIP válido.
Resposta do download alternativo: HTML `Site Unavailable / Unable to access this site.`
Não declarar teste visual aprovado nesta entrega. O HTML/rotas/templates são
exercitados pelo Flask; o script real do formulário também é executado via Node
com DOM mínimo, sem substituir a conferência visual no navegador instalado.
Windows/PostgreSQL e comparação visual continuam locais. Não foi executada toda
suíte do Tesseract; seleção proporcional aos contratos alterados.

### Fechamento da seleção

- Casos adicionais de permissão somente de lista e script real renderizado:
  `-m pytest tests/test_financeiro_policy_versions.py -k 'list_permission or real_template_js' -q --tb=short --show-capture=no -W error::sqlalchemy.exc.LegacyAPIWarning`:
  2 passed in 5.39s. O caso Node cobre 6 estados da expectativa oculta, inclusive
  ausência de formulário, seleção inicial, conflito preservado e troca de organização.
- Total distinto: **157 casos Python aprovados** (13 novos + 144 de regressão).
  A única falha inicial foi corrigida e seu caso reexecutado com aprovação.
- compileall, verificação sintática Node e git diff --check aprovados.

Empacotamento por git format-patch e aplicação git am --keep-cr em checkout
isolado da base de câmbio, com comparação da árvore e reverse --check antes
da disponibilização. Esses checks não substituem a conferência do banco local.
