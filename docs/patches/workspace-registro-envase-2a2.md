# Workspace — registro de envase 2A.2

Base: fixture RBAC validada pelo usuário (`a522be1` no checkout de entrega).
As correções dos combos e do carregamento de permissões estão validadas na
execução curta local. A nova etapa funcional aguarda testes e visual locais.

## O que mudou

Na aba Sessões, a preparação agora aceita data e tipo opcionais, mostra a
prévia existente e oferece **Registrar envase deste lote**. O modal padrão
explicita produto/litros e se haverá confirmação dos ingredientes pendentes.
Registro confirmado retorna à mesma sessão, inclusive antiga.

Rota nova:
`POST /brewstation/plant-workspace/<ID_PLANTA>/sessions/<ID_SESSAO>/register-envase`.
Recebe o token assinado emitido na prévia. Planta, sessão, material, litros,
data, tipo e chave da operação estão vinculados por assinatura; os valores
ocultos não são usados como fonte livre de contexto. Assinar a prévia não
escreve no banco nem movimenta estoque.

Permissões: `brew_sessions.list`, `envases.list`, `envases.create`.
Se os ingredientes ainda não foram confirmados, também exige
`brew_sessions.update`, como a confirmação já existente do lote.
Pendências de ingredientes são revalidadas pelo serviço no POST, com rollback.
Ingredientes confirmados não são baixados novamente nem têm custo recalculado.

## Regra única e repetição

O controller chama `envase_estoque_service.registrar_envase`, preservando o
consumo pelo `confirmar_consumo_ingredientes` e as embalagens por
`estoque_service.registrar_movimentacao(commit=False)`. Não altera saldos
ou ledger diretamente. A composição e os custos atuais são consultados no
registro; a prévia continua sendo estimativa sem reserva.

`Envase.idempotency_key` é opcional, com índice único no banco. Envases
antigos e callers existentes mantêm NULL. A chave é inserida antes de
qualquer consumo na mesma transação; se falhar movimento, log ou commit,
envase/chave/movimentos/confirmação desta tentativa são desfeitos.

Repetir o mesmo token devolve o mesmo envase, sem novas baixas ou log.
Uma colisão detectada no INSERT também recupera o registro original após
rollback. Chave existente com outros dados é rejeitada. Envase já cancelado
não é recriado pela repetição da chave. Consultas de pertencimento/permissão
continuam necessárias em cada requisição; a chave não concede autorização.

A proteção cobre a mesma intenção/token. **Consultar outra prévia gera nova
intenção**, permitindo envases adicionais iguais do mesmo lote. Os caminhos
antigos sem chave continuam funcionando, sem promessa de deduplicação nova
nesses formulários. Não reenviar como nova prévia para recuperar uma resposta
perdida: repetir a mesma confirmação. Se houver erro de rede, o token permanece
no formulário para retry. O SQLite pode rejeitar uma tentativa concorrente
por bloqueio; ela não confirma movimentos e pode ser repetida com o mesmo token.
A recuperação de colisão do índice é testada sem afirmar execução concorrente
real neste ambiente.

Após reservar a escrita por INSERT, o lote é relido para evitar flag de
confirmação antiga no identity map. O registro pelo workspace também adiciona
log da sessão com envase, material e usuário na mesma transação. Saídas de
embalagem recebem o usuário autenticado e preservam IDs de movimentação nos
snapshots. Os controles de sessão/status/timers/receita não são alterados.

Não introduz conversão de pacote para massa/volume, nem novo bloqueio por
saldo/composição vazia/unidades fracionadas; avisos da prévia permanecem e
regras centrais de estoque continuam decidindo a movimentação.

## Migration e aplicação

**Exige `flask db upgrade`** (no mesmo ambiente usado nos patches anteriores).
Revisão `e6274a913bc0`, pai `d5a81c4e09f2`.
Acrescenta coluna nullable e índice único em
`tesseract_brewstation_env_envase`, conferindo ambos quando create_all já
criou o esquema atual. Mantém IDs, envases antigos e histórico de migrations.
Faça o backup habitual do banco antes do upgrade; não apagar/recriar o banco.
Nenhum banco fornecido pelo usuário foi alterado para teste.

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-registro-envase-2a2.patch
flask db upgrade
```

## Testes

Primeiro, testes novos e migration isolada:

```powershell
python -m pytest tests/test_migration_envase_request_key.py tests/test_feature_envase.py tests/test_plant_workspace.py -k "request_key or chave_repetida or chave_falha or unique_key or falha_log or workspace_envase" -q
```

Depois, regressão das integrações:

```powershell
python -m pytest tests/test_plant_workspace.py tests/test_feature_envase.py tests/test_dashboard_runtime.py tests/test_recipe_timeline.py tests/test_precificacao_envase.py tests/test_addon_estoque.py tests/test_migrations_idempotent.py -q
```

Cobertura nova: repetição/chave conflitante, outra intenção válida, colisão do
índice no flush, rollback de movimentos e log, liberação da chave após falha,
token adulterado/contexto estrangeiro, permissões, pendências, retorno a lote
histórico e preservação de custo/status. Migration: SQLite antigo e esquema
já criado, repetição de upgrade, histórico intacto e unique/downgrade.

Na entrega foram executados AST Python, JSON, sintaxe JS dos scripts
alterados, balanceamento de blocos Jinja, diff e aplicação isolada do
format-patch com comparação de árvores. SQLite em memória confirmou UNIQUE
com múltiplos NULL. Isso não equivale a executar a migration Alembic nem a
renderizar a aplicação. **Pytest e migration Flask não executados** por falta
das dependências; validação local necessária.

## Roteiro visual

1. `/brewstation/plant-workspace/<ID_PLANTA>?tab=sessions&session_id=<ID_SESSAO>`:
   abrir lote histórico e Preparar envase. Selecionar produto e litros,
   opcionalmente data/tipo. Prévia não deve criar envase ou movimentar estoque.
2. Cancelar o modal de Registrar: nenhum envase, log ou movimento novo.
3. Confirmar com ingredientes já baixados: apenas embalagem é consumida,
   custo congelado permanece. Lista de envases deve mostrar o novo registro
   na mesma sessão; conferir snapshots no detalhe existente.
4. Repetir **o mesmo POST/token**, por exemplo reenviando a requisição no
   DevTools, sem consultar nova prévia: mesmo ID, mesmos movimentos/saldo e
   somente um log. Uma nova prévia é outra intenção, não é esse teste.
5. Lote com ingredientes não confirmados e resolvidos: modal informa consumo
   de ingredientes e embalagens; confirmar gera ambas na mesma transação.
   Operador sem permissão de confirmar ingredientes deve ficar bloqueado.
6. Lote com ingredientes pendentes: botão bloqueado; POST direto também
   falha sem gravação. Conferir resposta de erro e reabrir a mesma sessão.
7. Verificar temas claro/escuro, janela estreita, unidade PCT sem conversão
   inventada e retorno de sessão antiga. Preços/composição podem mudar entre
   consulta e registro, conforme aviso explícito.

## Pendências

2B (detalhes locais/estorno com retorno) continua pendente; estorno existente
permanece disponível na tela própria. Precificação ainda precisa alinhar
embalagens aos snapshots e insumos ao custo registrado, antes de considerar
custos/preço de venda consolidados. Dashboards avançados, sessões avançadas
e revisão de menus continuam no plano; nenhum menu foi ocultado nesta etapa.
