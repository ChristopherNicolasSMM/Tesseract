# Estoque — integridade do recebimento

Etapa posterior à validação do YeastBank, em 07/10/2026. Correção limitada
ao serviço manual de estoque; nenhum arquivo gerado ou modelo alterado.

## Achados corrigidos

- `fator_conversao_aplicado or 1.0` aceitava snapshot zero como fator 1.
- `quantidade_convertida_base or quantidade*fator` mascarava snapshot zero.
- Multiplicar quantidade e custo finitos podia produzir custo total infinito.

O recebimento rejeita fatores/quantidades não positivos ou não finitos e
preços negativos ou não finitos. Somente snapshots ausentes usam o fallback
legado. O fator cadastrado atualmente não substitui o snapshot histórico.
Falhas no recebimento continuam fazendo rollback de todas as entradas e
preservam o status confirmado. Ledger imutável e saldo atualizado pelo
serviço central permanecem os contratos existentes.

O teste de criação manual de saldo verifica o botão específico, evitando
falso positivo causado por traduções globais de outras telas.

## Verificações executadas

- Estoque: 149 casos passaram na execução ampla; o teste com falso positivo
  foi corrigido e passou na reexecução, junto com o novo caso legado.
  Total de 151 casos distintos validados. Os nove casos novos também
  passaram isoladamente.
- Envase, precificação e resolução de ingredientes: 177 testes passaram.
- Aplicação com `git am --keep-cr` sobre `d94f581`, igualdade de árvores
  e `git apply --reverse --check`: sem erros.

## Validação local

Não há migration; `flask db upgrade` não é necessário para este patch.

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-estoque-integridade.patch
python -m pytest tests/test_addon_estoque.py tests/test_feature_envase.py tests/test_precificacao_envase.py tests/test_mash_control_ingredient_resolution.py -q
```

Conferir `/estoque/materials`, `/estoque/movimentacaos` e `/estoque/saldos`.
Receber um pedido confirmado com dois pacotes de fator 25: saldo +50 unidades
base e custo unitário dividido por 25. Repetir recebimento deve ser recusado
pelo status recebido. Em pedido de teste com snapshot inválido, conferir
recusa, status confirmado e ausência de novas movimentações.

## Encerramento e limites

Receita/planta/Brewfather e YeastBank foram validados pelo usuário. Este
último pacote foi aplicado e validado localmente pelo usuário, incluindo seus
testes, conforme confirmação de abertura da fase 3 em 07/10/2026. Ciclo encerrado
no escopo entregue; ver [inventário da fase 3](fase3-inventario-e-sequencia.md).
A revisão cobre regressões automatizadas dos fluxos existentes de estoque,
consumo de ingredientes, envase e precificação; não é auditoria exaustiva
de concorrência, contabilidade ou segurança.

Integração física/custos de culturas YeastBank, financeiro/câmbio, recebimento
parcial e revisão concorrente de compras permanecem frentes futuras. Não
recalcula custos congelados, não muda unidade-base histórica e não adiciona
novos fluxos de estorno.
