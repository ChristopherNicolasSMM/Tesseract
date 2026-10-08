# Fase 3 — taxas e histórico de conversão

Base do repositório `5f26a1a`, contendo corretivo financeiro validado pelo usuário
e os três patches Reports. AddonFinanceiro 1.1.0: modelos/controllers/APIs e
transações descobertos pelo AddonBase, sem arquivos gerados alterados.

## Entrega

- Taxas direcionais por organização, data, fonte e tipo manual/contratual.
- Cálculo Decimal com prévia sem gravação e confirmação idempotente.
- Snapshot do valor original/convertido, produto, taxa, política e autoria.
- Telas com selects padrão, toolbar/paginação, preservação do formulário inválido
  e histórico nos temas claro/escuro. API paginada, escrita somente admin.
- Migration `d04f1a65c239`, parent `c93e0f54b128`, sem migração de valores legados.

O pacote avança a etapa de taxas/conversão/histórico. Políticas monetárias
versionadas ainda não foram implementadas: a inicial permanece imutável.
Mudança de moeda-base não pode reinterpretar operações/saldos existentes.
Integração compras/estoque, moeda em cotação/pedido, recebimento convertido,
títulos/contas/liquidações e conciliação continuam entregas futuras.

## Aplicar e validar em PowerShell

Com árvore limpa, pare a aplicação e execute no ambiente habitual:

```powershell
git -c gc.auto=0 am --keep-cr .\tesseract-fase3-financeiro-cambio.patch
python run.py db upgrade
python -m pytest tests/test_financeiro_exchange.py tests/test_financeiro_foundation.py tests/test_financeiro_ui_integrity.py tests/test_migrations_idempotent.py tests/test_migration_schema_compat.py -q
```

Reinicie a aplicação e use Ctrl+F5. Requer o schema Reports c93e0f54b128 presente
na base publicada do repositório. Downgrade bloqueado se houver taxa/conversão.
Não executar downgrade para corrigir cálculo; registros preservam história.

Roteiro: cadastrar USD e BRL (se ainda ausentes), política BRL da organização,
taxa USD → BRL 5.25 em data escolhida e fonte demonstrativa; simular 10.01 USD
na mesma data, confirmar 52.55 BRL. Verifique prévia sem novo registro, histórico
com 52.5525 antes do arredondamento, fonte/autor/política e menus automáticos.
Moeda-base usa taxa vazia. Taxa de outro dia/organização deve dar erro preservando
formulário. APIs retornam o registro existente em reenvio com mesma chave/dados.

Rotas: `/financeiro/exchange-rates/` e `/financeiro/conversions/`.
[Manual](../../addons/addon_financeiro/docs/manual/02-cambio.md) e
[contrato](../../addons/addon_financeiro/docs/technical/02-cambio.md).

## Limites de validação

SQLite e navegador Chromium via fixture Flask em memória. Windows/PostgreSQL e
versões exatas do requirements dependem de conferência local. Nenhuma instalação
ou upgrade de dependências feito. Não há integração cambial externa.

## Evidências de validação

Python utilizado: `/workspace/scratch/3a31c61fc128/venv-corretivo/bin/python`.

- `-m pytest tests/test_financeiro_exchange.py -q --tb=short`:
  39 passed in 311.56s antes da adição dos casos finais.
- `-m pytest tests/test_financeiro_exchange.py -k 'unique_collision or inactive_organization or decimal_contract' -q --tb=short -W error::sqlalchemy.exc.LegacyAPIWarning`:
  13 passed in 15.13s, 39 deselected. Total novo: 52 casos distintos aprovados.
- `-m pytest tests/test_financeiro_foundation.py tests/test_financeiro_ui_integrity.py tests/test_migrations_idempotent.py tests/test_migration_schema_compat.py -q --tb=short -W error::sqlalchemy.exc.LegacyAPIWarning`:
  91 passed e 1 failed in 357.70s. Única falha: teste anterior exigia exatamente
  duas entradas de menu; reconciliado para quatro entradas e rotas explícitas.
- Reexecução de `tests/test_financeiro_ui_integrity.py::test_menu_uses_defaults_and_retires_only_own_obsolete_leaf` com os mesmos filtros:
  1 passed in 19.19s. Total da regressão: 92 casos distintos aprovados, incluindo
  cadeia real de upgrade e downgrade vazio via subprocess Flask.
- `TEST_PYTHON=<python> TEST_CHROMIUM=<chromium> node tests/test_financeiro_exchange_browser.cjs`:
  fluxo aprovado, sem pageerror, com captura e inspeção dos temas claro/escuro.
  Rede do navegador atendida pelo Flask test_client; sem servidor de produção.
- compileall e git diff --check aprovados.

Total distinto: **144 casos Python aprovados**, mais o fluxo Chromium.
Não houve reexecução integral de todas as suítes do projeto. O patch aguarda
validação no ambiente do usuário. Aplicação isolada e igualdade da árvore são
conferidas no empacotamento; não equivalem a teste do banco instalado.
