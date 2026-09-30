# Confirmação de ingredientes dentro da sessão

A aba Sessões permite confirmar ingredientes pelo card Ingredientes e custo
do lote, sem abrir o CRUD da sessão. Usa o modal Bootstrap padrão do Core
(`window.__tesseractConfirm`) com a tradução existente para essa ação.
Não usa seletor/modal nativo nem duplica o listener declarativo de confirmação.
Enquanto o modal ou o envio estiver ativo, o botão bloqueia cliques repetidos.

O botão está disponível com `brew_sessions.update` e só habilita quando há
receita vinculada sem pendências. A validação na tela não substitui a do
servidor. A rota POST verifica sessão, planta, lixeira e permissão antes de
chamar `confirmar_consumo_ingredientes`, o mesmo serviço usado pelo fluxo
existente e pelo fallback do envase. Nenhuma regra de movimentação é duplicada.

O serviço continua responsável pela conferência, conversão para unidade-base,
baixa via regra única de estoque, custo congelado e confirmação transacional.
Falhas no consumo desfazem as movimentações da tentativa. Repetir uma
confirmação já concluída devolve o resultado registrado, sem outra baixa.
A ação não muda status, timers ou etapas da sessão.

Após sucesso, o workspace recarrega o fragmento atual, preservando a seleção
e a paginação do histórico. Exibe a mensagem da ação e o custo registrado.
Se houver erro, mantém o formulário e permite corrigir/tentar novamente.
Consultar a aba ou abrir o modal não movimenta estoque.

A rota nova é:
`POST /brewstation/plant-workspace/<ID_PLANTA>/sessions/<ID_SESSAO>/confirm-ingredients`

A confirmação na tela completa da sessão continua disponível. Não há
migration nem alteração de menus. Controllers/services gerados não foram
editados.

## Verificação

Abrir `http://localhost:5000/brewstation/plant-workspace/<ID_PLANTA>?tab=sessions`.
Selecionar um lote não confirmado, conferir os ingredientes, abrir o modal,
cancelar e verificar que não houve baixa. Confirmar pelo modal e conferir
o custo e o saldo. Num lote com pendência, o botão deve estar desabilitado.

```shell
pytest tests/test_plant_workspace.py tests/test_weak_ref_value_field.py tests/test_feature_envase.py
```

Os testes novos verificam a rota com ledger/saldo reais, idempotência,
rollback em falha da segunda baixa, pendências, receita ausente, pertencimento
à planta, lixeira e permissões. Sintaxe Python/JavaScript e aplicação do patch
são verificadas neste ambiente; pytest e revisão visual precisam rodar no
ambiente do projeto.
