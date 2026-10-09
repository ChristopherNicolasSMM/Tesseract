# Fase 3 — prévia de ingredientes por organização

Base: `ffb4603`, após cotação organizacional/transferências. Primeira etapa da
integração de produção: consulta de disponibilidade e custo da receita por
organização explícita. Sem migration; reiniciar servidor.

## Aplicação

```powershell
git am --keep-cr .\tesseract-fase3-brewstation-previa-organizacional.patch
python -m pytest tests/test_organization_recipe_preview.py tests/test_feature_envase.py tests/test_mash_control_ingredient_resolution.py -q
```

## Uso e contrato

Na aba Receita do workspace, abrir uma receita e clicar **Consultar ingredientes
por organização**. Selecionar uma organização ativa com política monetária.
URL direta: `/brewstation/plant-workspace/<planta>/receitas/<receita>/estoque-organizacional`.
Usar IDs reais. Query `organization_code=<codigo>&format=json` retorna JSON.
Sem organização, tela mostra seletor e API retorna 422. Organização inválida,
inativa ou sem política: 422. Planta/receita removida/inexistente: 404.
Exige login, `recipe_steps.list` e `saldos.list`.

A receita permanece compartilhada; a escolha vale somente para a consulta.
Não grava vínculo na planta, receita ou lote. Soma todas as linhas resolvidas
do mesmo material antes de comparar necessidade/saldo. Ingredientes ignorados
não entram no consumo estimado; pendências de resolução/conversão são avisadas.
Saldo global e outras organizações não cobrem uma falta. Exibe moeda-base.
Não presume custo zero quando material está sem saldo; saldo positivo com custo
zero é válido. Total soma apenas materiais estimáveis e avisa quando incompleto.
`custo_completo` e `estoque_suficiente` são condições distintas: pode existir
custo estimável e saldo insuficiente.

Valores/quantidades retornam strings decimais em JSON. Custo estimado usa valor
total/quantidade do saldo, sem arredondar primeiro pelo custo médio exibido.
Cálculo Decimal com contexto de 64 dígitos; nenhuma taxa/conversão automática.
Quantidades/conversões da receita ainda são Float no cadastro legado: adapta-se
a representação decimal disponível, sem recuperar precisão anteriormente perdida.

## Limites e sequência

Consulta não congela custo, não reserva saldo e não cria movimentos. Estado
pode mudar com operações posteriores; não garante disponibilidade futura.
**Confirmação do lote e envase permanecem no fluxo global legado**, como
informado na própria tela. Próxima etapa: vínculo explícito/imutável do lote,
baixa organizacional atômica/idempotente e custo/moeda originais; depois envase
e reconciliação explícita. Sem migração automática de saldos/lotes.
Títulos financeiros permanecem posteriores.

## Verificação

Cobertura nova: agregação de material repetido, falta por organização,
separação do legado, pureza, custo Decimal/zero, pendentes/ignorados,
organização obrigatória/inativa/sem política, receita removida, JSON/tela,
link na receita e autorização. Regressões: envase/consumo, resolução de
ingredientes e workspace de receita. Resultado informado na entrega após
execução. Patch aplicado em checkout isolado da base para conferir árvore.
Sem certificação de PostgreSQL, hardware ou inspeção visual em navegador.
