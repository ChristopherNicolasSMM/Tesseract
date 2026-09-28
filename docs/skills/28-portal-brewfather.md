# 28 — Portal de sincronização Brewfather

## Situação atual e primeira entrega

**[EXECUTADO]** A integração anterior tinha `GET /disponiveis` com
seleção de receitas, mas lia apenas as primeiras 50, não filtrava e
mantinha o comando de importar todas na barra do histórico. O portal
`/brewstation/brewfather-syncs/portal` substitui essa entrada visual.
`/disponiveis` continua funcionando como endereço antigo.
O acesso ao portal é exibido no cabeçalho do histórico: o link fica
declarado no hook `_acoes_em_massa_extra.html` e o JS dessa extensão
o posiciona fora da barra de seleção do CrudGen, que permanece oculta
enquanto nenhuma linha do histórico está marcada.

O portal consulta as páginas de receitas (até 500 por acesso), aplica
filtros por nome, estilo, tipo e situação, mostra novas, importadas e
apagadas, e aceita selecionar até 50 receitas por operação. Receitas
importadas continuam intactas: marcar uma receita existente não seria
uma atualização. A operação busca detalhes somente dos IDs escolhidos.
Falha na obtenção do detalhe impede criar uma receita vazia; falha
durante a gravação reverte a receita parcial e registra o erro.

O limite de 500 é declarado na tela quando atingido; nesse caso os
filtros alcançam só o conjunto carregado. A API v2 oferece paginação
`start_after` e ordenação, porém não busca por nome, estilo ou pasta na
lista de receitas. A listagem e os filtros deste portal são locais.
Para evitar novas chamadas a cada filtro, a lista bruta fica em cache
no processo por 90 segundos; o botão **Atualizar lista** força uma nova
consulta. O status de importação continua consultando a base local.
As credenciais permanecem no servidor (`BREWFATHER_USER_ID`,
`BREWFATHER_API_KEY`); a chave precisa de `recipes.read`.

## Matriz de fluxos

| Origem | API v2 | Destino atual | Política |
|---|---|---|---|
| Receitas | `/recipes` e `/recipes/:id` | `MashRecipe`, ingredientes, etapas e água | Importação seletiva; sem sobrescrever receita existente |
| Lotes | `/batches` e `/batches/:id` | Ainda sem importador de lotes Brewfather | Exibir e selecionar em etapa própria, após definir vínculo e idempotência com `BrewSession` |
| Inventário | `/inventory/{fermentables,hops,yeasts,miscs}` | Estoque/ledger do Tesseract | Exibir e fazer de-para antes de qualquer conciliação; nunca atribuir saldo direto |

## Consulta de lotes e inventário [EXECUTADO]

O portal tem abas de consulta para lotes e para fermentáveis, lúpulos,
leveduras e outros ingredientes. Cada aba de inventário consulta apenas
sua coleção; lotes aceitam filtro de status na API. A busca textual de
ambos e o filtro por quantidade informada são aplicados localmente nas
páginas carregadas. Há limite visível de 500 registros por consulta,
cache de 90 segundos e atualização manual.

São necessários os escopos `batches.read` para lotes e `inventory.read`
para inventário, além de `recipes.read` para receitas. A quantidade de
inventário é mostrada como valor bruto recebido: **nenhuma conversão de
unidade é inferida**, nenhum saldo do Tesseract é atualizado e nenhum
lote é criado. A API de inventário não lista itens padrão sem edição
ou quantidade cadastrada; uma lista vazia não prova ausência de um
ingrediente no catálogo completo do Brewfather.

`BrewSession` não tem identificador remoto de lote nem regra de
correspondência com uma receita Brewfather. Estes requisitos devem ser
resolvidos antes de permitir importação seletiva de lotes. Para o
inventário, o passo seguinte é um de-para explícito de item remoto,
Material e unidade, acompanhado de uma prévia de diferença de saldo e
movimentação identificada no ledger caso o usuário confirme.

**[ABERTO]** No inventário, definir a fonte de verdade do saldo, a
unidade, a identificação do material, o tratamento de diferenças e a
auditoria da movimentação antes de oferecer importação. Para lotes,
definir se a seleção cria novo lote ou associa um existente e como
tratamos versões de receita. Nenhum desses fluxos escreve dados nesta
primeira entrega.

Referência: [documentação oficial da API v2](https://docs.brewfather.app/api)
(consultada em 2026-09-28). A API lista receitas com `limit` máximo 50
e pagina por `start_after`; lotes aceitam filtro de `status` no
servidor. A documentação informa limite atual de 500 chamadas/hora
por chave e recomenda tratar HTTP 429 e `Retry-After`.
