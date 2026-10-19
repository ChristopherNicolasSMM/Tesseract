# Consolidação do Financeiro — entrega 2 de 3

Base: primeira entrega de workspace `1d1ed6e`. A main remota consultada estava
em `437896e`; aplique o patch de workspace antes deste se ele ainda não estiver
no seu checkout. Esta entrega acrescenta competência e DRE gerencial; gráficos
de resultados, integração automática de custos e fechamento são a entrega 3.

## Aplicação

```powershell
git am --keep-cr .\tesseract-financeiro-competencia-dre-entrega2.patch
python run.py db upgrade
python -m pytest tests/test_financeiro_accrual.py tests/test_financeiro_workspace.py tests/test_financeiro_treasury.py tests/test_financeiro_cash_operations.py tests/test_financeiro_reports.py tests/test_reports_emission.py tests/test_reports_library.py tests/test_financeiro_ui_integrity.py -q
node tests/js/test_financeiro_workspace.cjs
```

Migração `f82cad560b94`, parent `e71b9d45fa83`. Reinicie a aplicação após o upgrade.
Não são reconhecidos valores do legado automaticamente. Conceda explicitamente
financial_results.list aos perfis de consulta pertinentes; escritas são admin.
O menu permanece com uma entrada de workspace e os endpoints anteriores continuam.

## Conteúdo

- Classificação de categorias com versão, vigência mensal, motivo e snapshot.
- Apropriação mensal e rateio por centro, conservando exatamente o valor base.
- Reconhecimento único do principal; componentes das baixas são origens próprias.
- Ajustes manuais documentados, reduções e estorno integral rastreável.
- Revisão assistida de origens sem competência/classificação, sem datas presumidas.
- DRE mensal/acumulada com centro, subtotais e composição navegável.
- Modelo Reports financeiro-dre, fonte pública DTO e emissão HTML com valores reais.

Compras de estoque só admitem exclusão patrimonial nesta fase, para não duplicar
compra/pagamento/produção/custo. O demonstrativo sempre informa seu caráter parcial.
Estado atual por competência: estornos reapresentam meses originais, sem lançar
caixa ou fingir reconstrução histórica de uma data anterior. Ajustes administrativos
com referências diferentes exigem revisão humana de possível evidência duplicada.

## Validação local

1. Abra Financeiro > DRE e resultados e selecione organização e período.
2. Classifique uma categoria de despesa e outra de receita com vigência mensal.
3. Revise um título, aproprie 100,01 em 33,33 e 66,68 em dois meses/centros e
   confirme a prévia. O total deve ser conservado e o saldo bancário inalterado.
4. Pague parcialmente o título e confira que o principal da DRE não se repete.
5. Reconheça juros/descontos/FX da baixa pelas origens específicas e grupos
   financeiros compatíveis. Nenhum componente zero deve aparecer como pendência.
6. Estorne o reconhecimento, reapresente e confira o histórico. Para cancelar
   título ou estornar baixa com componentes reconhecidos, reverta antes os
   respectivos reconhecimentos. Principal não precisa sair da DRE só porque
   um pagamento foi estornado.
7. Confira DRE por mês/centro e composição. Altere classificação atual e confirme
   que o reconhecimento anterior mantém o grupo e versão registrados.
8. Publique o exemplo financeiro-dre na IDE Reports, gere HTML e confira valores,
   organização, meses completos e indicação parcial.

Manual: addons/addon_financeiro/docs/manual/07-competencia-dre.md.
Contrato: addons/addon_financeiro/docs/technical/07-competencia-dre.md.

## Resultado conferido

144 casos distintos selecionados passaram: 23 de competência/DRE, 62 de
Tesouraria/Reports e 59 de workspace/operações bancárias/relatórios/interface.
Checks finais afetados por pequenos ajustes de schema/formulário foram repetidos.
Seis cenários concorrentes verificaram classificação repetida, reconhecimento
idempotente, disputa da mesma origem, estorno repetido, cancelamento concorrente
de título e estorno concorrente de baixa. Prévia/consulta executaram somente
SELECT; caixa e estoque não são alterados pelos reconhecimentos.

Upgrade completo sobre esquema inicializado, upgrade repetido, criação isolada,
rejeição de schema incompatível antes de DDL e downgrade protegido com dados
foram conferidos. O aviso de reflexão SQLite sobre model_definition do Core não
impediu a cadeia de upgrade. Execução Linux/SQLite; sem certificação nativa
Windows/PostgreSQL ou inspeção visual em navegador. Sem novas dependências.

Patch aplicado com git am --keep-cr em checkout isolado da base 1d1ed6e,
verificação reversa e igualdade de árvore conferidas. Sem publicação remota.
