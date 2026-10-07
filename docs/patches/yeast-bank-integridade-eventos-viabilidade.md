# YeastBank — integridade de eventos e viabilidade

Pacote corretivo sobre `fbb227e`, após validação da consolidação de receita,
planta e Brewfather. Reúne os achados YB-01 a YB-07 da auditoria.

## Alterações

- Os sete services do YeastBank foram regenerados pelo template atual do
  CrudGen, que já possui overrides. Os hooks delegam as escritas ao serviço
  manual `yeast_integrity_service`; nenhuma regra foi colocada em arquivo gerado.
- Criação de evento e seus efeitos usam um único commit. Contagem automática
  recebe item/evento e o evento recebe a contagem na mesma transação; descarte
  grava status anterior/posterior, data e motivo no item. Falha desfaz tudo.
  `post_create_redirect` faz somente navegação; repeti-lo não cria outra contagem.
- Item/tipo de evento registrado são imutáveis. O status posterior de um
  descarte também é imutável. Observações podem ser revisadas, sem regravar o
  motivo original do descarte. A contagem vinculada não pode migrar para outro
  item. Lixeira/restauração de histórico não reativa uma cultura nem reaplica
  o efeito de descarte.
- Cepas/dispositivos/containers com dependentes fora da lixeira não podem ser
  apagados. Referências precisam existir e estar fora da lixeira, inclusive a
  cadeia dispositivo → container → item. Restaurar exige os pais disponíveis;
  exclusão permanente recusa referências, incluindo registros históricos.
  Não há cascata. Histórico de item/evento pode ficar arquivado separadamente.
- Percentuais ficam em 0–100; contagens são inteiros não negativos; quadrados,
  diluição e volume alvo são positivos; números não finitos são rejeitados.
  Validar/salvar/restaurar configuração usa rollback e mensagem amigável,
  inclusive conflito com outro tipo ativo. Notas e campos enviados no formulário
  continuam preservados em erro, pelo controller padrão.
- Ao editar entradas brutas de contagem com resultados preenchidos, limpe os
  três resultados para recalcular ou informe resultados revisados. O serviço
  rejeita a reutilização silenciosa dos resultados anteriores. Resultados
  manuais permanecem quando a entrada bruta não muda.
- O recálculo exclui itens/contagens/starters na lixeira. Contagens cujo evento
  de origem esteja apagado, seja de outro item ou tenha tipo incompatível não
  são referência. Starters `planned`, `active` e `discarded` são ignorados;
  `completed` é elegível se não contaminado e com resultado válido. **Legados
  já persistidos sem status** continuam elegíveis; novos starters sem status
  são gravados como `planned`. Não houve conversão automática do histórico.
- Mantida prioridade real → estimado → starter → referência inicial da cepa,
  com modelo linear existente. Pais apagados/ausentes impedem recálculo do item.
  Sem referência, a estimativa antiga e seus campos de origem são limpos. O
  recálculo é transacional e sua rota informa falha sem deixar atualizações
  parciais. Alterar referências/lixeira não dispara recálculo automaticamente;
  o operador usa a ação já existente quando desejar atualizar estimativas.
- Painel exige `yeast_bank_items.list`, inclusive seu menu. Abas de cepas/eventos
  e atalhos dependem de permissões próprias. JS não chama listas sem autorização
  e não mostra atalhos de criação/edição proibidos. Para contagem automática,
  exige também `yeast_cell_count_histories.create`; o atalho do painel requer
  `.detail` para abrir a contagem. O service aceita gravação sem essa permissão
  de leitura, mas o hook não redireciona para uma tela proibida.
- Reenvio do formulário de contagem é bloqueado enquanto sai da página; refresh
  via bfcache limpa detalhes antigos. Isso não é idempotência entre POSTs
  independentes: duas novas criações deliberadas continuam sendo dois eventos.
- Identificação do item resolve os IDs atuais de cepa/container, evitando nome
  antigo quando a relationship já estava carregada em cache.

## Limites

Não movimenta estoque, não recalcula custos de lote, não cria cultura filha,
reserva ou inoculação. Integração econômica, genealogia e reutilização física
continuam exigindo desenho funcional próprio. As listas do painel continuam
sem paginação server-side nesta entrega. Eventos não recebem nova trilha de
revisões; a correção protege os efeitos já existentes, sem ampliar o schema.

**Sem `db upgrade`: nenhuma migration ou alteração de schema.** Reiniciar a
aplicação atualiza código e sincronização normal do menu. Perfis que usam o
painel devem possuir leitura de itens, além das permissões das abas/ações.

## Aplicar e validar

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-yeast-bank-integridade.patch
python -m pytest tests/test_yeast_bank_integrity.py tests/test_phase5_yeast_bank.py tests/test_phase5b_yeast_bank_full.py tests/test_phase14_yeast_container.py tests/test_yeast_bank_painel.py tests/test_viability_engine.py -q
node tests/js/test_yeast_bank_permissions.cjs
```

**Validação executada:** 106 testes Python na regressão conjunta (81 existentes
e 25 novos), mais dois casos complementares de erro do recálculo e permissão
de criação sem acesso ao detalhe, todos aprovados. Teste JavaScript funcional
aprovado para permissões, ações ocultas e bloqueio de reenvio; sintaxe Python,
JS, Jinja e diff conferidos. Aplicação `git am` em checkout isolado sobre o
commit-base conferida, com árvore idêntica ao commit entregue. A validação usa SQLite; não comprova concorrência de
manutenção em múltiplos processos ou comportamento em PostgreSQL. Não há
validação de sensores/dispositivos ou consumo físico nesta entrega.

## Roteiro visual

1. `/brewstation/yeast-bank/painel`: conferir abas, links e legibilidade nos dois
   temas. Repetir com usuário limitado: sem leitura de itens, painel recusado;
   com leitura de itens/eventos, mostrar Eventos sem Cepas; sem leitura de
   contagens, não solicitar essa API.
2. `/brewstation/yeast-bank-events/`: criar contagem vinculada e editar seu
   resultado. Criar starter planejado com resultado; recalcular, concluir o
   starter e recalcular novamente. A conclusão torna a referência elegível.
3. Tentar trocar item/tipo de evento existente ou item da contagem vinculada:
   deve recusar e preservar os registros. Em uma contagem calculada, mudar
   entradas e limpar os três resultados para recalcular.
4. `/brewstation/yeast-cell-count-histories/`: tentar percentual acima de 100,
   contagem negativa ou quadrados zero. Formulário deve manter os dados e
   apresentar erro. Valores válidos e resultados manuais devem continuar aceitos.
5. Descartar cultura com motivo; revisar notas do evento, apagá-lo e restaurá-lo.
   Cultura continua descartada, com motivo original preservado.
6. `/brewstation/yeast-containers/` e `/brewstation/yeast-storage-devices/`:
   container ocupado/dispositivo com container ativo recusam lixeira. Arquivar
   dependentes primeiro e restaurar pais primeiro; testar exclusão permanente
   quando existe referência histórica.
7. `/brewstation/yeast-bank-configs/`: arquivar uma configuração, criar outra do
   mesmo tipo e tentar restaurar a antiga. Deve recusar sem quebrar a próxima
   gravação.
8. `/brewstation/yeast-bank-tools/recalculate-viability`: após arquivar a última
   leitura, recalcular e conferir fallback. Itens arquivados não são alterados.

Aplicado e validado localmente pelo usuário. A revisão final do estoque foi
entregue e também validada; a sequência atual está no
[inventário da fase 3](fase3-inventario-e-sequencia.md).
