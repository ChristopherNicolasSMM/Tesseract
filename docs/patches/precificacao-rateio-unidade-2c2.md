# Entrega 2C.2 — Rateio e preço por unidade

## Escopo

A precificação com envase selecionado aplica a regra já usada no custo de
industrialização: custo dos ingredientes do lote × litros do envase / soma
dos litros dos envases registrados não apagados. Cancelados são excluídos.
Embalagens continuam usando o snapshot daquele envase (2C.1). Sem envase,
o cálculo continua sendo do lote inteiro, sem preço por unidade/litro.

Tela apresenta denominador, fator, custo do lote, unidades, custo/preço por
unidade e preço por litro. A quantidade de ingredientes exibida é da receita
completa; apenas seu custo aplicado é rateado. Unidades fracionárias seguem
o contrato existente, sem arredondamento para inteiro. Lucro/IPI/ICMS usam
as fórmulas existentes. Consultar/simular não escreve ou movimenta estoque.

Novos envases congelam produção (material, volume em litros por unidade,
unidades geradas). O registro mantém transação, rollback e idempotência
existentes; repetição preserva o primeiro snapshot. Cadastros posteriores
não alteram as unidades registradas. Envase legado sem snapshot estima
unidades pelo volume explícito atual via API pública do estoque, identificado
na tela. Sem volume válido, preço unitário fica indisponível. Snapshot
presente inválido é rejeitado, sem substituir histórico por estimativa.

Calcular e Salvar persiste base do rateio: escopo, participantes/volumes,
fator, origem dos custos/unidades e valores unitários. Novo registro ou
estorno muda novos cálculos, sem reescrever salvos. Vincular posteriormente
um cálculo do lote a um envase não transforma sua base: calcule novamente
com o envase selecionado para rateio. Históricos antigos não são reconstruídos.
Volumes inválidos em participantes bloqueiam o rateio. Custos/percentuais e
resultados não finitos/negativos são rejeitados. Sem inferência PCT/massa/volume.

## Aplicação

Requer patch 2C.1 já aplicado e **db upgrade**. Migration `f8c214ab709e`
(parent `e6274a913bc0`) adiciona dois JSONs nullable: `Envase.producao_snapshot`
e `CalculoPrecificacao.base_calculo_snapshot`. Inspeciona colunas para
compatibilidade com create_all. Sem backfill, limpeza de banco ou stamp.
Faça backup normal antes de migrar. Não testar downgrade no banco de uso;
downgrade remove os novos snapshots, preservando demais campos/linhas.

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-precificacao-rateio-unidade-2c2.patch
python -m flask db upgrade
python -m pytest tests/test_precificacao_envase.py tests/test_feature_envase.py tests/test_migration_precificacao_basis.py tests/test_migrations_idempotent.py tests/test_plant_workspace.py -q
```

## URLs e roteiro visual

- `/brewstation/plant-workspace/<ID_PLANTA>?tab=sessions&session_id=<ID_LOTE>&envase_id=<ID_ENVASE>`
- `/brewstation/precificacao-envase/?lote_id=<ID_LOTE>&envase_id=<ID_ENVASE>`

1. Use lote de teste com ingredientes confirmados, custo R$100 e dois
   envases ativos de 20 e 30 L. Para o de 20 L, conferir 20/50 = 40%,
   ingredientes R$40 e somente as embalagens daquele envase.
2. Se o produto registrado tem 0,5 L por unidade, conferir 40 unidades.
   Com embalagens R$10 e lucro 20%, impostos zero: subtotal R$50, total
   R$60, custo/unidade R$1,25, preço/unidade R$1,50, preço/litro R$3,00.
3. Simular e conferir que não houve baixa ou novo envase. Salvar e conferir
   que apenas cálculo/itens foram gravados, mantendo ledger/saldos.
4. Alterar o volume do produto: novo cálculo daquele envase preserva as
   40 unidades registradas. Envase antigo sem snapshot identifica estimativa
   atual ou indisponibilidade, sem aparentar unidades históricas confirmadas.
5. Estornar o outro envase pelo modal padrão com motivo: novo cálculo do
   primeiro passa para 20/20 e ingredientes R$100. O cálculo salvo antes
   conserva R$40 e sua base de 50 L. Cancelado não aparece como elegível.
6. Abrir sem envase: total de ingredientes do lote, sem preço unitário.
   Conferir indicação de estimativa antes de confirmar ingredientes e
   legibilidade nos temas claro/escuro e em tela estreita.

## Validação e pendências

Executados neste ambiente: 99 testes aprovados em precificação, envase e
migration específica; 28 aprovados (110 deselected) no recorte de envase/
precificação do workspace. A execução anterior incluindo toda a cadeia
`test_migrations_idempotent.py` teve 96 aprovados; depois foram adicionados
casos de valores extremos e volume legado inválido, cobertos nos 99 testes.
Sintaxe Python/Jinja/JavaScript e `git diff --check` verificadas. Não houve
teste visual em navegador. Roteiro acima deve ser validado localmente pelo usuário.
Etapa 2C.2 implementada, aprovação local pendente. Etapas avançadas de
sessões, dashboards e menus continuam pendentes; nenhuma remoção de acesso.
