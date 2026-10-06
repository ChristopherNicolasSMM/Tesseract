# Revisão integrada — receita até envase e estorno

Base: descanso visual 3A.2 validado pelo usuário. Esta entrega reúne correções
de geração/consumo/navegação e testes do percurso. Não reimplementa fluxos já
validados e não declara todos os cadastros avançados incorporados.

Aplicado e validado pelo usuário em 06/10/2026. A pendência posterior de
items → UN é tratada em pacote separado de conversões por material.

## Inventário e correções

| Frente | Código/evidência conferida | Resultado desta revisão |
| --- | --- | --- |
| Saneamento/revisão | ingredient_sanitation_service e ingredient_resolution_service; suíte de resolução | Preservar vínculo local, proteção de receita usada e cópia de revisão; sem novo de-para global |
| Geração | recipe_timeline_service.generate_session_from_recipe e rota manual | Rollback explícito de sessão/etapas em falhas de flush/commit; valida receita disponível, planta ativa e nome até 100 no serviço |
| Navegação após geração | _tab_recipe_detail.html | Bloqueia reenvio enquanto aguarda e evita abrir aba Sessões após fragmento removido; erro libera nova tentativa |
| Confirmação | ingredient_consumption_service.confirmar_consumo_ingredientes | Reserva escrita antes de reler confirmação; preserva ledger/saldo centrais e custo congelado; receita apagada/inexistente bloqueia novo consumo |
| Envase | envase_preparation_service, envase_estoque_service | Preservar prévia sem baixa, token idempotente, snapshots e estorno atômico existentes |
| Precificação | precificacao_service e envase_cost_basis | Preservar custo confirmado, origem dos snapshots, rateio e distinção de estimativa; simulação sem estoque |
| Histórico/contexto | plant_workspace, precificacao e testes de workspace | Preservar seleção de sessões antigas, pertencimento, permissões e retorno ao lote |

## Consistência e concorrência

A função pública de confirmação continua sendo o único ponto de confirmação.
Antes de uma confirmação pendente, executa UPDATE sem modificar custo ou
updated_at para obter a reserva de escrita SQLite. Releitura com
populate_existing evita estado antigo no identity map. Quem aguardou outra
confirmação recebe o custo congelado, sem outra saída. Não existe baixa direta
ou atualização paralela de saldo; registrar_movimentacao continua central.

commit=False mantém reserva, saídas e marcação na transação externa do envase.
Falha faz rollback de toda essa transação; retentativa é permitida. Lote já
confirmado pode devolver seu custo mesmo se a receita foi apagada depois;
apenas consumo novo exige receita disponível. Consulta não adquire essa reserva.
Teste com duas conexões reais em banco SQLite temporário sintético confirma
uma baixa. Não é teste sobre o banco fornecido ou do usuário. Não adiciona
retry automático para database locked; falha deve ser tratada e repetida após
rollback, sem efeito parcial.

Geração continua criando uma sessão por pedido explícito. O bloqueio AJAX
previne reenvio durante a espera, mas não é chave persistente de idempotência
para geração. Repetir uma geração concluída cria outra sessão. Sessão/etapas
são confirmadas juntas; erro inesperado retorna mensagem do projeto e não
uma cópia parcial. Status inicial continua draft/active.

## Testes novos

- Nome inválido, planta inativa/apagada e receita apagada na geração.
- Falhas de flush/commit deixam zero sessões/etapas; receita intacta e nova
  tentativa funciona. Rota responde JSON 500 com mensagem compreensível.
- Consumo com receita apagada não baixa nem congela custo.
- commit=False seguido de rollback desfaz ledger, saldo e marcação; nova
  tentativa confirma uma vez.
- Duas conexões SQLite com identity maps aquecidos confirmam um único consumo.
- Percurso receita/timeline → sessão copiada → prévia/simulação sem baixa →
  confirmação/custo congelado → envase/token repetido → simulação → estorno.
  Estorno devolve embalagem, preserva consumo dos ingredientes e snapshots;
  repetição não devolve novamente. Histórico e precificação permanecem acessíveis.
- Node: envio AJAX único, retorno para sessão criada, erro e fragmento removido.

## Aplicação e comandos

Sem db upgrade: nenhum schema ou migration alterado. Aplicar após 3A.2.

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-revisao-integrada-processo.patch
python -m pytest tests/test_plant_workspace.py tests/test_recipe_timeline.py tests/test_feature_envase.py tests/test_precificacao_envase.py tests/test_mash_control_ingredient_resolution.py tests/test_addon_estoque.py -q
node tests/js/test_workspace_recipe_generation.cjs
```

## Roteiro visual

Usar receita e materiais de teste, com saldo/unidade/conversões cadastrados.

1. /brewstation/plant-workspace/: escolher planta. Abrir Receita e selecionar
   receita com timeline e ingredientes; corrigir pendências pelo fluxo local.
2. /brewstation/plant-workspace/<PLANTA>?tab=recipe&recipe_id=<RECEITA>:
   criar revisão quando a receita estiver protegida; lotes antigos mantêm vínculo.
3. Gerar sessão como rascunho; conferir retorno à aba Sessões e etapas copiadas.
   Em falha, mensagem e formulário liberado; nenhuma cópia parcial.
4. /brewstation/plant-workspace/<PLANTA>?tab=sessions&session_id=<SESSAO>:
   conferir estimativa/pêndencias, confirmar ingredientes e conferir custo
   registrado. Repetição não pode gerar outra saída.
5. Preparar envase e simular custos: nenhuma baixa só por consultar. Registrar
   explicitamente; conferir snapshots e ledger no detalhe do envase no lote.
6. /brewstation/precificacao-envase/?lote_id=<SESSAO>&envase_id=<ENVASE>:
   conferir rateio/preço unitário e retornar ao mesmo lote. Cálculo salvo
   preserva a base registrada; novos cálculos seguem a produção ativa.
7. Estornar com motivo e confirmação padrão: devolve embalagens, preserva
   consumo/custo dos ingredientes, operador, movimentos e snapshots.
8. Abrir sessão antiga fora da primeira página e repetir consultas/retornos;
   testar filtros, usuário limitado, planta externa e temas claro/escuro.

Não houve teste com API Brewfather, dispositivos físicos ou validação visual
em navegador nesta entrega. Não inclui novas operações de manutenção avançada,
PID contínuo, proveniência física dos eventos ou novos menus. Brewfather e
YeastBank permanecem frentes de auditoria futuras; nenhuma alteração remota.


## Verificação executada

Suíte ampliada dos seis arquivos indicados: **594 passed**, em 843,07 segundos.
Node de geração AJAX passou. Testes focados do percurso, concorrência SQLite,
rollback e mensagem da rota também executados. Sintaxe Python/Jinja/JavaScript,
diff e aplicação do format-patch em checkout isolado conferidos.
Não foi executada a suíte completa do repositório nem teste visual/hardware.
