# Auditoria do YeastBank — 07/10/2026

Base auditada: `fbb227e` (consolidação receita/planta/Brewfather), validada pelo
usuário. Escopo autorizado nesta etapa: auditoria, reprodução das lacunas e
planejamento do pacote corretivo. Nenhuma regra operacional foi alterada.

## Resultado

O fluxo de cadastro, armazenamento, eventos, contagens e estimativa existe.
Foram confirmadas lacunas de integridade que justificam um pacote corretivo
antes de encerrar esta frente. O YeastBank não implementa atualmente um fluxo
operacional de consumo de culturas em sessões ou de custeio de propagação.

### Achados reproduzidos

| ID | Prioridade | Evidência e efeito | Correção proposta |
| --- | --- | --- | --- |
| YB-01 | Alta | `viability_engine.best_viability_reference_for_item` aceita uma contagem com `is_deleted=True`: retornou `count_history_real`, em vez do fallback válido. `recalculate_all` também alterou a estimativa de um item na lixeira. A leitura do código confirma a mesma ausência de filtro para starters. | Excluir registros na lixeira das consultas operacionais. Conferir o evento de origem da contagem, sem eliminar históricos. Definir o efeito de lixeira/restauração na estimativa. |
| YB-02 | Alta | Starter com resultado 99 e status `planned` ou `discarded` foi utilizado como referência, mesmo sem conclusão válida. | Usar resultado de starter concluído e não contaminado. Tratar resultados legados sem status de forma explícita, preservando o histórico. Manter a prioridade real → estimado → starter → cepa já estabelecida no projeto. |
| YB-03 | Alta | O service confirma o evento antes do hook `post_create_redirect`. Ao injetar erro no `flush` que cria a contagem, rollback deixou um evento já persistido sem contagem. Descarte também usa um segundo commit para alterar o item. | Serviço manual para criação e efeitos na mesma transação; hook de controller cuida apenas da navegação. Web/API devem chamar a mesma regra. Testar rollback, repetição e falhas dos efeitos. |
| YB-04 | Alta | PUT de evento de contagem alterou `bank_item_id`, mas a contagem automática permaneceu no item anterior. | Bloquear a mudança do item/tipo de eventos com efeitos já registrados, ou implementar operação explícita de correção que mantenha todos os vínculos e histórico. Não migrar efeitos silenciosamente. |
| YB-05 | Alta | `YeastContainerService.trash` aceitou container com item vivo. POST da API também cadastrou novo item em container apagado (HTTP 201). | Verificar referências na manutenção e validar pais ativos no servidor. Abranger cepa → item e dispositivo → container → item; restauração deve respeitar os pais, sem cascata automática. |
| YB-06 | Alta | Neubauer com 120 vivas e −20 mortas produziu 120% de viabilidade. POST de contagem aceitou `viability_percent=150` (HTTP 201). O cálculo usa `squares_counted or 5`, tratando zero como ausência. | Validar números finitos, contagens não negativas, quadrados/diluição positivos e percentuais em 0–100. Aplicar limites em services manuais/hooks, antes de persistir, tanto na API quanto no formulário. Definir recálculo ao editar entradas sem apagar resultados manuais. |
| YB-07 | Média | A leitura da rota `/brewstation/yeast-bank/painel` confirmou ausência de checagem de permissão de leitura; o probe inicial dessa página usou uma URL de API incorreta e foi corrigido durante a implementação. A rota exige login, mas não permissão de leitura. As APIs possuem decoradores próprios, portanto esse caso não comprova vazamento dos dados protegidos. | Aplicar uma política de acesso ao painel e construir abas/ações conforme permissões. Contagem automática precisa de regra explícita de autorização da operação composta; testar perfis restritos. |

Os probes da auditoria produziram nove falhas na primeira rodada e duas na
complementar. Dez reproduzem violações; a outra era uma URL de painel incorreta.
YB-07 fica fundamentado na leitura do código original. Os cenários foram
incorporados, com a rota e a injeção de falha ajustadas, à suíte corretiva
`tests/test_yeast_bank_integrity.py`. Usam apps SQLite isolados, sem banco de produção.

## Lacunas funcionais e limites

- **Propagação:** Starter guarda datas, volume alvo, objetivo, status e resultado.
  Não há criação rastreável de cultura filha, genealogia de gerações ou consumo
  de uma quantidade física. O registro de evento não equivale a executar essa
  operação em estoque.
- **Reutilização e brassagem:** `lot_code` da contagem é texto livre. Não há FK
  operacional de cultura/evento para receita ou sessão, nem contrato de reserva,
  inoculação, coleta e estorno. As referências ao YeastBank encontradas em
  controllers externos são comentários do gerador, não integração funcional.
- **Custos/estoque:** os models da feature não contêm vínculo com Material,
  saldo ou snapshot econômico; os services examinados não chamam o serviço
  central de movimentação. Não há baixa duplicada do YeastBank demonstrada;
  há ausência de um fluxo de baixa/custo nesta feature. Custos de levedura do
  BrewStation seguem o ingrediente/material, não a cultura física do banco.
- **Painel:** carrega listas completas e filtra itens/contagens no navegador.
  Filtros de API não são utilizados nesse percurso. Paginação/busca e
  preservação de seleção merecem melhoria, mas são secundárias aos vínculos.
- **Descarte e histórico:** editar/apagar/restaurar o evento não reaplica nem
  estorna automaticamente o efeito no item. Definir correção explícita e
  rastreável; não transformar remoção de histórico em reativação automática.
- **Configuração:** a restauração genérica da configuração não trata no service
  o conflito do índice de tipo ativo com rollback/erro amigável. Este ponto
  foi identificado por leitura; precisa de teste específico no pacote.

## Pacote corretivo recomendado

Reunir YB-01 a YB-07 em **um patch de integridade e usabilidade do YeastBank**:

1. Services manuais para eventos e manutenção, reutilizados por web/API,
   preservando arquivos gerados pelo CrudGen.
2. Validação laboratorial, consultas de viabilidade coerentes com a lixeira e
   ciclo de vida do starter, sem mudar silenciosamente o modelo linear.
3. Vínculos protegidos, efeitos atômicos, restauração validada e autorização
   por ação; confirmação/modal/seletores/hints conforme os componentes Core.
4. Manuais, testes de regressão e dos cenários reproduzidos, roteiro visual,
   patch `git format-patch` e conferência de aplicação em checkout isolado.

Essas correções podem usar o schema existente; a ausência de migration deverá
ser conferida na implementação. Genealogia, inoculação, coleta, saldo físico e
custeio não devem ser prometidos como já disponíveis. Se incorporados ao ciclo,
precisam de desenho próprio de unidades, vínculos e estorno, e possivelmente
migration, sempre pela regra central de estoque.

Depois da validação do patch corretivo, executar a revisão final de estoque
planejada. A auditoria do YeastBank não substitui essa revisão.

## Validação e reprodução

Regressão existente concluída: **81 passed, 3 warnings em 148,89 segundos**,
com as cinco suítes abaixo. Os probes adicionais retornaram nove falhas em 15,40 segundos e duas em
7,45 segundos; a ressalva da rota incorreta está registrada acima.
Sintaxe dos dois scripts do painel conferida com `node --check`.
Ambiente de teste reconstruído, Python 3.12.14 / Flask 3.1.3 /
Flask-SQLAlchemy 3.1.1 / SQLAlchemy 2.0.51. Não se afirma aprovação
da suíte completa do projeto.

```powershell
python -m pytest tests/test_phase5_yeast_bank.py tests/test_phase5b_yeast_bank_full.py tests/test_phase14_yeast_container.py tests/test_yeast_bank_painel.py tests/test_viability_engine.py -q
# No pacote corretivo, os cenários de auditoria estão nesta suíte:
python -m pytest tests/test_yeast_bank_integrity.py -q --tb=short --show-capture=no
```

Inspecionados models, services, hooks, APIs, controllers, painel JS e referências
externas da feature. Não houve validação em navegador, equipamentos reais ou
PostgreSQL; os testes executados usam SQLite. Aparência, interação nos temas e
comportamento com base real permanecem no roteiro do pacote corretivo.

Rotas locais principais para esse roteiro:

- `/brewstation/yeast-bank/painel`
- `/brewstation/yeast-bank-items/`
- `/brewstation/yeast-bank-events/`
- `/brewstation/yeast-cell-count-histories/`
- `/brewstation/yeast-containers/`
- `/brewstation/yeast-storage-devices/`
- `/brewstation/yeast-bank-configs/`
- `/brewstation/yeast-bank-tools/recalculate-viability`

## Continuidade

Pacote corretivo autorizado em 07/10/2026; ver
[implementação e roteiro](yeast-bank-integridade-eventos-viabilidade.md).

Atualização de 07/10/2026, abertura da fase 3: pacote corretivo aplicado e
validado localmente pelo usuário. A revisão final de estoque também foi
entregue e validada. Achados acima descrevem o estado auditado anterior à
correção; não são uma nova lista de defeitos pendentes. Lacunas físicas e
econômicas permanecem propostas, conforme [fase 3](fase3-inventario-e-sequencia.md).
