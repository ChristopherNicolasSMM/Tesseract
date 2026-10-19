# Consolidação do Financeiro — entrega 1 de 3

Base atualizada da main: `437896e`, com as três entregas financeiras anteriores.
Workspace compartilhado em `/financeiro/`, dashboard operacional, filtros de
contexto e navegação integrada de títulos, caixa/bancos, conciliação e ajustes.
Não implementa a DRE: competência e resultado são as próximas duas entregas.

## Aplicação

```powershell
git am --keep-cr .\tesseract-financeiro-workspace-dashboard-entrega1.patch
python -m pytest tests/test_financeiro_workspace.py tests/test_financeiro_treasury.py tests/test_financeiro_cash_operations.py tests/test_financeiro_ui_integrity.py tests/test_financeiro_reports.py tests/test_reports_emission.py tests/test_module_discovery.py -q
node tests/js/test_financeiro_workspace.cjs
```

**Sem migração adicional / sem db upgrade para este patch.** As migrações das
entregas anteriores precisam estar aplicadas. Reinicie a aplicação para o boot
sincronizar as transações e desativar os atalhos substituídos. Não foi publicado
no repositório remoto; patch preparado e aplicado em checkout isolado.

## Validação funcional local

1. Abra Financeiro > Workspace financeiro. Selecione organização e período.
2. Confira saldos e cartões; clique em vencidos, abertos e próximos vencimentos.
3. Abra um título, confira parcelas e registre uma baixa parcial. O retorno
   permanece no detalhe com organização e datas. Confira a origem na lista
   de pagamentos/recebimentos e teste o estorno.
4. Consulte contas/lançamentos, fluxo e transferências na mesma área. A conta
   escolhida filtra os lançamentos; previsões não são distribuídas por conta.
5. Importe e concilie um extrato de teste. Confira preservação do contexto,
   indicação de erro e desfazimento rastreável, sem alteração dos saldos.
6. Acesse categorias/centros e ajustes monetários pela área Configurações.
7. Gere relatório contextual com um modelo já publicado. Confira organização
   e datas e utilize o retorno ao Financeiro.
8. Valide aparência em claro/escuro, telas menores e gráficos interativos.
   Tabelas e tooltips devem conservar valores exatos. O teste visual em
   navegador não pôde ser executado neste ambiente: o download Chromium
   retornou arquivo inválido (`End of central directory record signature not found`).

## Compatibilidade e limites

Permissões de origem e escritas administrativas continuam vigentes. As rotas
antigas permanecem operacionais, agora sob o mesmo shell. Os 13 atalhos antigos
são desativados pelo manifesto Financeiro; Reports desativa apenas os atalhos
financeiros substituídos pelos botões de emissão. Não apaga transações/permissões.

A descoberta padrão de models/controllers permanece. O Core apenas acrescenta
suporte opcional a `workspaces` no manifesto, validando endpoints registrados.
Addons sem o campo mantêm seu catálogo anterior; overrides manuais permanecem.
Um teste antigo de descoberta foi atualizado para reconhecer que Reports já
compõe explicitamente `super().get_transactions()` com emissões, portanto sua
transação automática é intencional e não representa duplicação.

As pendências e classificações de parcelas são atuais, não uma reconstituição
histórica. Não há apuração de lucro, competência presumida ou DRE nesta entrega.
Relatórios recebem organização/período; o botão declara esse escopo, sem prometer
aplicar filtros de busca/conta/pendência não suportados pela fonte.

Manual: addons/addon_financeiro/docs/manual/06-workspace-dashboard.md.
Contrato: addons/addon_financeiro/docs/technical/06-workspace-dashboard.md.

## Resultado conferido

238 casos distintos selecionados passaram: 28 de workspace/descoberta, 53 de
tesouraria/interface/relatórios e 157 de operações bancárias/fundação/câmbio/
políticas. O teste antigo de redirect da entrada financeira foi atualizado
para o novo workspace (HTTP 200) e repetido com sucesso. Checks afetados por
ajustes finais de contexto, conta, tema e emissão foram repetidos.

O teste JavaScript real passou para preservação de contexto, tema, escape de
rótulos e tooltips monetários exatos. Dashboard executou somente SELECT e não
alterou saldos/títulos/movimentos. A suíte bancária verificou a cadeia Alembic
existente, sem nova revisão. Execução Linux/SQLite; sem certificação nativa de
Windows/PostgreSQL ou inspeção visual em navegador.

Patch conferido por git am --keep-cr em checkout isolado de 437896e, igualdade
de árvore e git apply --reverse --check. As próximas entregas permanecem:
competência/DRE e, depois, dashboard de resultados/integração de custos.
