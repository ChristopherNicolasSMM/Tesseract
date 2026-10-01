# Workspace — preparação e prévia de embalagens (2A.1)

01/10/2026. Base: revisão 1C aplicada e validada pelo usuário; checkout
comparado com `origin/main` (`fc99d35`), sem divergência de conteúdo.
2A.1 implementado, aguardando pytest e visual locais. Registro 2A.2 e
estorno local 2B não são considerados integrados por esta entrega.

## Escopo

O card Envase e precificação da aba Sessões passa a oferecer **Preparar envase
deste lote**. Produto pelo combo padrão `materials`, litros positivos e GET
para prévia local, preservando sessão/planta e filtros da aba. Mostra volume
por unidade, unidades físicas sem arredondamento, composição agrupada por
componente, necessidade, saldo atual e estimativa de embalagem pelo custo médio.

Custo ausente não é mostrado como zero conhecido: subtotal é parcial. Composição
vazia, material componente indisponível/inativo, saldo ausente/insuficiente,
unidade-base não cadastrada e unidades fracionadas têm avisos. Unidade é a da
base cadastrada ou identificação existente do material, sem conversão automática
da composição. PCT não ganha tamanho presumido. Esta prévia não modifica regras
de saldo negativo do serviço central; o aviso não reserva nem bloqueia estoque.

O custo registrado dos insumos do lote inteiro aparece separadamente e é
preservado, sem rateio/recalcular receita confirmada. Antes da confirmação,
a prévia informa que o registro pelo fluxo existente faria consumo automático
de ingredientes e mostra o aviso de pendências. Não chama confirmação.

O serviço manual novo `envase_preparation_service.preparar_envase()` usa
lookups públicos do estoque e a função de volume do serviço existente.
Não cria envase, ledger, saldo, snapshot, token ou reserva. Não chama `commit`,
`flush`, registro ou estorno. A consulta pode ser repetida sem baixas.

## Por que separar registro do incremento

`registrar_envase()` já faz fallback de ingredientes e baixa de composição
numa transação com rollback. Ainda não possui chave/proteção de repetição de
criação no servidor. A próxima integração 2A.2 precisa dessa proteção, além
de conferir custos na continuidade da precificação. O motor de preço de
venda existente ainda lê `ItemEnvase` para embalagem e recalcula insumos;
não usar essa tela como prova de custo congelado/snapshot. A nova prévia
consulta embalagem atual e não calcula preço de venda nem custo industrial
registrado. Estorno rastreável existe no detalhe, mas integração local e
retorno ao lote ainda ficam no 2B. Nenhum menu foi ocultado.

## Rotas e permissões

Substitua os IDs reais (incluindo um lote antigo para conferir o contexto).

| Método | URL | Uso |
| --- | --- | --- |
| GET | `/brewstation/plant-workspace/<ID_PLANTA>?tab=sessions&session_id=<ID_LOTE>` | Abrir lote no workspace |
| GET | `/brewstation/plant-workspace/<ID_PLANTA>/tab/sessions?session_id=<ID_LOTE>` | Fragmento existente, com preparação no card |
| GET | `/brewstation/plant-workspace/<ID_PLANTA>/sessions/<ID_LOTE>/prepare-envase?material_resultante_id=<ID_MATERIAL>&quantidade_litros=10` | Nova consulta JSON `ok/html`, acionada pelo formulário |
| GET | `/brewstation/precificacao-envase/?lote_id=<ID_LOTE>` | Atalho existente, separado da prévia de embalagens |

Nova rota exige login, `brew_sessions.list`, `envases.list` e `envases.create`.
Sem acesso à criação, o formulário fica oculto. Planta/sessão apagadas,
sessão de outra planta e produto inexistente/apagado/inativo retornam 404.
Campos malformados, litros não positivos/não finitos, volume inválido e
composição inválida retornam 400. Permissão negada retorna 403. Falha inesperada
retorna 500 com mensagem genérica; não troca silenciosamente de sessão.
POST na nova rota é 405: não existe ação de gravação nesse endpoint.

## Aplicação, banco e testes

```powershell
git am --keep-cr .\brewstation-preparacao-envase-2a1.patch
python -m pytest tests/test_feature_envase.py tests/test_plant_workspace.py
python -m pytest tests/test_weak_ref_value_field.py tests/test_addon_estoque.py tests/test_dashboard_runtime.py
```

**Não precisa de `flask db upgrade`**. Nenhuma alteração de schema/migrations,
CrudGen ou cadastro gerado. Manuais de mostura/envase, primeiros passos, FAQ,
documentação técnica, backlog e plano atualizados, com 1C validado registrado.

Novos testes: cálculo por volume (inclui ML), composição repetida, unidades
fracionadas, custo zero conhecido versus ausente, produto/composição inválidos,
contexto/RBAC, preservação de lote/custo, nenhuma chamada de consumo/registro/
movimentação/commit, repetição sem gravar e erro genérico.

Verificação pelo assistente: sintaxe Python, scripts JavaScript, diff e aplicação
via `git am --keep-cr` em checkout isolado. Pytest não executado aqui; o usuário
executará localmente. Renderização Jinja e testes com aplicação em execução
não foram realizados no ambiente do assistente.

## Roteiro visual e resultado esperado

1. Na URL da casca, abra lote antigo e expanda **Preparar envase deste lote**.
   O lote deve permanecer selecionado mesmo que não esteja na primeira página.
   Busque material ativo com Volume Real e composição; referências vêm da API
   do combo, não de opções completas pré-carregadas no HTML.
2. Exemplo: produto com volume 500 ML, componente 1 UN por unidade e 10 L.
   Prévia deve mostrar 0,5 L/unidade, 20 unidades e 20 UN do componente.
   Com custo médio R$ 2,00, embalagem estimada R$ 40,00 (sem somar preço de venda).
3. Repita a consulta. Confira ledger/saldo e lista de envases: nenhuma mudança.
   Ingredientes não confirmados devem continuar assim. Em lote confirmado,
   custo registrado e horário da confirmação devem continuar iguais.
4. Sem preço médio, confira **Não disponível** e **estimativa parcial**. Sem
   composição, confira aviso e estimativa parcial de R$ 0,00. Isso não significa embalagem
   gratuita. Com saldo menor que a necessidade, confira aviso sem nova baixa.
5. Informe volume que resulte em fração de unidade: mostrar fração e aviso,
   sem arredondar consumo. Selecione unidade de pacote no cadastro sem inventar
   equivalência em kg/L; a prévia não cria conversões.
6. Altere produto ou litros: resultado anterior deve desaparecer. Faça isso
   durante consulta e troque de aba: resposta antiga não deve reaparecer em
   outro lote/aba. Reabra e teste combo, claro/escuro e largura menor.
7. Teste material sem volume, litros zero/negativos ou dados inválidos na rota:
   erro legível, resultado antigo limpo e nenhum registro/baixa parcial.
   Sessão de outra planta/apagada deve retornar 404; produto inativo também.
8. Sem `envases.create`, formulário oculto e consulta 403. Sem `envases.list`,
   card existente continua respeitando sua permissão. Confira navegação para
   precificação e retorno ao mesmo lote, sem considerar a prévia como envase.

## Próximos incrementos

2A.2: idempotência de registro no servidor, continuação de custos e confirmação
com efeitos de estoque explícitos; avaliar migration se necessária. 2B:
detalhes/snapshots e estorno local com motivo/modal/operador e retorno ao lote.
3–6: dashboards avançados/manutenção, operações restantes e revisão de menus.
Os caminhos atuais de registro/estorno continuam acessíveis. Reconhecimento
de alarmes, revisão de receitas e consumo central não foram refeitos.
