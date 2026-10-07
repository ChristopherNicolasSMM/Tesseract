# Fase 3 — compras e recebimento protegido

Base: `05939c3`, depois da reconciliação documental aplicada pelo usuário.
Pacote funcional de C1/C2 do inventário, com proteção do saldo compartilhado.
Aplicado e validado localmente pelo usuário, incluindo os testes do pacote.

## Defeitos reproduzidos

Antes da correção, quatro casos de `test_purchase_integrity.py` falharam:
edição de quantidade de item confirmado, troca do fator histórico ao salvar
os mesmos dados, status recebido atribuído pelo CRUD sem entrada de estoque
e lixeira de item recebido. Reprodução inicial: **4 failed em 6,75 s**.
Não atribuir esse resultado à concorrência: os testes concorrentes foram
adicionados para conferir a implementação em conexões independentes.

## Contratos implementados

- Pedido novo começa em rascunho. Preservado o atalho existente de API/serviço
  rascunho → confirmado, além de rascunho → enviado → confirmado. Cancelamento
  permitido antes do recebimento. Não há retorno de estado nem reabertura de
  cancelado/recebido. O único caminho de confirmado para recebido é o serviço
  de entrada de mercadoria; payload de CRUD não lança estoque nem muda esse estado.
- Dados do cabeçalho (número, fornecedor, transportadora, datas, condição e
  frete) congelam após sair do rascunho. Observações continuam editáveis e
  não refazem custos ou snapshots. Campos enviados com o mesmo valor permanecem
  aceitos; transições permitidas não exigem edição dos demais campos.
- Itens só são criados/editados em rascunho. Não podem migrar para outro pedido.
  Pai precisa estar ativo; unidade ativa precisa pertencer ao material ativo.
  IDs/quantidades/preços booleanos ou inválidos, valores não finitos,
  quantidade não positiva, preço negativo e overflow são recusados com rollback.
- Salvar o item, alterar preço ou quantidade preserva o fator já registrado.
  Somente troca explícita de material/unidade em rascunho toma novo fator.
  Quantidade convertida/subtotal acompanham os dados planejados editados.
  Payload de snapshots ou relationships não contorna readonly/anotações.
  Legado sem fator não recebe o fator atual por reenvio: mudança de quantidade/
  preço exige novo item ou troca explícita de unidade válida em rascunho.
- Lixeira/restauração de itens exige pedido ativo em rascunho ou cancelado;
  referência em ledger ou cotação impede manutenção do item. Pedido só pode
  ser arquivado/restaurado em rascunho ou cancelado, sem recebimento registrado.
  Arquivar itens antes do pai e restaurar pai antes dos itens. Exclusão permanente
  de pedido recusa qualquer item, inclusive apagado; não há cascata destrutiva.
- Recebimento reserva a linha do pedido com UPDATE sem mudança semântica e
  relê estado/itens. A reserva permanece na transação das entradas e do status.
  Pedido já recebido é recusado; vínculos de ledger também recusam nova entrada
  se um status legado tiver sido alterado indevidamente. Falha desfaz entradas,
  saldo novo e status. Recebimento continua **total**.
- Toda movimentação central reserva o material antes de consultar/criar seu
  saldo e relê o saldo, inclusive com identity map aquecido. Isso protege
  recebimentos de pedidos diferentes e a criação do primeiro saldo. Ledger,
  quantidade e custo médio continuam na mesma transação. Cálculos que deixam
  quantidade/custo/valor acumulado não finitos são recusados com rollback.
- Timeout/conflito de escrita produz erro tratável e rollback; não há retry
  automático nem commit intermediário. SQLite serializa escritores; em
  PostgreSQL o UPDATE reserva a linha. A concorrência PostgreSQL não foi testada.

## Arquitetura e geração

Regras em `purchase_integrity_service.py` e overrides dos hooks manuais.
Dois services de compras regenerados pelo template atual, sem edição manual
de arquivos gerados. Template de service ganhou filtros por FK no `list`,
preservando o filtro contextual de itens por pedido antes customizado no
gerado. Somente os dois services foram regenerados; controllers, APIs e
HTML existentes não foram reescritos. Não há nova permissão ou rota.

Fixtures antigas que semeiam pedidos já confirmados/recebidos usam criação
direta de itens históricos, em vez de comandos CRUD agora proibidos. A suíte
nova testa explicitamente os bloqueios do serviço, API e formulário, além
de rollback e concorrência real em SQLite temporário.

**Sem migration; não executar `flask db upgrade` por este patch.** Sem mudança
de schema, moeda, unidade-base ou recalculo de custos de lotes anteriores.

## Aplicação e testes

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-fase3-compras-recebimento-protegido.patch
python -m pytest tests/test_purchase_integrity.py tests/test_addon_estoque.py tests/test_feature_envase.py tests/test_precificacao_envase.py tests/test_mash_control_ingredient_resolution.py tests/test_phase4_crudgen.py -q
```

Resultados finais: **188 passed em 212,73 s** (151 de estoque e 37 casos
novos); após adicionar dois cenários complementares, **230 passed em
239,31 s** (39 novos e 191 de envase, precificação, resolução e CrudGen).
Total: **381 casos distintos aprovados**, sem confundir reexecuções com casos
novos. Os cinco cenários concorrentes usam SQLite em arquivo, conexões
independentes e identity maps aquecidos.

Ambiente: Python 3.12.3, Flask 3.1.3, Flask-SQLAlchemy 3.1.1, SQLAlchemy
2.0.51 e pytest 9.1.1. Não houve upgrade de dependências. Dois services
conferidos como idênticos ao template; nove arquivos Python analisados e
28 links locais válidos. Aplicação isolada, igualdade de árvores e verificação
reversa são exigidas antes de disponibilizar o patch; resultados na entrega.
Não chamar aprovação local antes do retorno do usuário. SQLite sintético,
nunca banco fornecido.

## Roteiro visual

Reinicie a aplicação após aplicar. Substitua IDs pelos registros de teste.

1. `/estoque/pedido-compras/`: criar pedido rascunho; abrir
   `/estoque/pedido-compras/<ID_PEDIDO>`. Na aba Itens, adicionar material e
   unidade explícita PCT com fator 25, quantidade 2 e preço 100. Esperar 50
   unidades-base e subtotal 200. Manter PCT como código, sem conteúdo embutido.
2. Em rascunho, salvar preço/quantidade sem mudar unidade: fator registrado
   permanece. Unidade de outro material ou números inválidos são recusados.
3. Enviar/confirmar: edição de item ou cabeçalho protegido deve mostrar erro;
   observações continuam salvando. As telas existentes ainda podem mostrar
   botões/campos de edição: o bloqueio é no servidor, com mensagens; este pacote
   não redesenha os formulários. Conferir mensagem legível nos dois temas.
4. Registrar Entrada de Mercadoria no confirmado. Esperar +50 unidades-base
   e custo 4 por unidade-base, supondo saldo inicial zero. Lote/validade seguem
   opcionais. Repetir ação, inclusive de outra aba já aberta, deve ser recusado
   sem novas entradas. `/estoque/saldos` e `/estoque/movimentacaos` mostram resultado.
5. Pedido/item recebido: tentar alteração de preço, fator, quantidade, estado
   e lixeira. Histórico permanece. Notas no cabeçalho podem mudar sem custo novo.
6. Em pedido rascunho sem referências: arquivar item, arquivar pedido, tentar
   restaurar filho antes do pai (recusa); restaurar pai e filho. Exclusão do
   pedido com item histórico deve recusar. Itens originados de cotação podem
   ter manutenção bloqueada para preservar o vínculo, mesmo em rascunho.
7. Conferir `/brewstation/plant-workspace/` e fluxo de envase já existente:
   prévia sem movimentos, registro/estorno mantendo custos congelados.

## Limites e próximas entregas

Não valida PostgreSQL, hardware, Brewfather remoto ou comportamento visual em
navegador. Operações podem sofrer timeout/deadlock e exigir nova tentativa;
não se promete espera ilimitada. SQL direto/modelos fora dos serviços não
participam destas proteções. Múltiplos materiais em operações externas podem
obter locks em ordens diferentes; rollback mantém atomicidade, sem retry.
Numeração automática por último ID continua sujeita a conflito entre criações
concorrentes; unicidade do banco recusa uma tentativa, sem gerar outro número.

Não é auditoria completa do RFQ: geração de pedidos de cotação ainda tem
commits por service e concorrência/atomicidade próprias a investigar. Este
pacote protege o pedido/item criado e seu recebimento, não promete geração
RFQ atômica ou idempotente. Também não protege manutenção concorrente do
cadastro de fatores/unidade-base: permanece U1, próximo pacote. Recebimento
parcial, câmbio/financeiro e culturas físicas permanecem sem implementação.
