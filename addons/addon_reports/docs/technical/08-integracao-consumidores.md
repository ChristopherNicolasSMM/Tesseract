# Integração Python e contextual — contratos pilotos v1

Os adaptadores pertencem ao addon que possui os dados. Reports recebe JSON
e revalida `report_templates.render`; não importa ORM de Estoque/BrewStation.
Não há FKs entre addons. O detalhe do saldo e a aba Sessões usam ações opcionais
com modal Bootstrap e eventos delegados; sem Reports ativo o bloco não aparece.
Os serviços são acessíveis em Python; o transporte genérico existente é
`POST /api/reports/render`, com autenticação e token `X-Reports-CSRF` obtido em
`GET /api/reports/session`.

## Estoque

`addons.addon_estoque.root.services.report_data_service.build_stock_report_data(material_id=None)`
retorna `{contract: "estoque.saldos.v1", items: [...]}`. Exige `saldos.list` e
`materials.list`. Apenas saldos e materiais não excluídos, ordenados por nome/id;
materiais sem saldo não aparecem. Uma consulta com join evita N+1.
O filtro opcional `material_id` restringe a um material (400 se inválido, 404
se não existir saldo elegível). O botão do detalhe sempre envia esse filtro;
não exporta a tabela inteira sem avisar.

Quantidade, custo médio, valor total e limites são strings decimais ou `null`.
O valor total registrado não é recalculado como quantidade × custo. A conversão
de Float existente não recupera precisão perdida no armazenamento e não altera
o ledger. Unidade de medida e filtros ficam para evolução do contrato.

## BrewStation

`addons.addon_brewstation.features.feature_mash_control.services.report_data_service`
expõe `build_session_report_data(session_id, plant_id=...)`, retornando
`{contract: "brewstation.session.v1", session: {...}, steps: [...]}`.
Exige `brew_sessions.list`, `brew_plants.list` e `brew_session_steps.list`.
Planta excluída, sessão excluída ou sessão de outra planta retorna 404. Passos
excluídos não aparecem; os demais são ordenados por índice/id.

O custo é `custo_total_insumos` já registrado, inclusive `null` antes de
confirmação. Zero não significa dado ausente. Não se lê receita atual para
simular histórico, nem se executam polling, alarmes ou reconciliação. `recipe_id`
é identificação, não snapshot. Os passos podem ter sido editados: este DTO é
uma leitura dos registros atuais da sessão, não um documento histórico imutável.

## Emitir HTML e PDF opcional

```python
from addons.addon_estoque.root.services.report_data_service import generate_stock_report

# Request autenticado; finalizar previamente qualquer transação de negócio.
html = generate_stock_report("estoque.saldos", version=1, parameters={})
```

Para brassagem, usar `generate_session_report("brewstation.session", session_id,
plant_id=plant_id, version=1, parameters={})` do módulo descrito acima.
As funções importam Reports apenas no momento da emissão. Sua utilização exige
Reports ativo; não há instalação automática nem dependência obrigatória no boot.
Checagens de domínio usam `current_user.has_permission` e os erros HTTP do Core
(400/401/403/404/413); erros de
composição/emissão usam `ReportError` do contrato central.

Os builders usam uma sessão de leitura própria e não fazem commit, rollback ou
autoflush da sessão do consumidor. Por isso retornam somente dados persistidos.
A emissão central rejeita alterações pendentes do consumidor com 409. Antes de
emitir, o chamador deve concluir explicitamente sua transação. Leitura independente
não garante isolamento entre várias consultas em todos os bancos; snapshot
transacional estrito e concorrência de edição serão avaliados na etapa PostgreSQL.
Mais de 2000 itens/passos resulta em 413, evitando truncamento silencioso.

## Preparar templates de demonstração

`examples/estoque-saldos.json` e `examples/brewstation-session.json` contêm layout,
schema, dados fictícios e parâmetros. Não são seeds e não alteram templates
existentes. O operador cria um template na IDE e usa **Carregar exemplo**,
confirmando a substituição do rascunho, ou usa a API:

1. POST `/api/reports/templates` com chave/nome.
2. GET `/api/reports/templates/{id}/versions/1` para obter `lock_version`.
3. PUT na mesma URL com os quatro campos do exemplo e o `lock_version` atual.
4. Prévia e publicação explícitas pelos endpoints existentes ou pela IDE.

As chaves sugeridas são `estoque.saldos` e `brewstation.session`; não sobrescrever
uma chave já utilizada. Os exemplos não aplicam formatação monetária: mostram
valores registrados como texto e preservam o branco de impressão. O canvas
continua respeitando a folha azul acinzentada no tema escuro.

## Evidência e evolução

Testes em `tests/test_reports_consumers.py` verificam custo registrado, zero/null,
exclusão, ordem, escopo por planta, autorização e preservação de alterações
pendentes. Exemplos são validados e compostos pelo mesmo serviço da produção.
O teste de navegador percorre os dois botões até a prévia HTML e o acionamento de impressão; testes HTTP
validam contrato, publicação, CSRF, RBAC, indisponibilidade e escopo por planta.
Filtros avançados, unidades, formulário de parâmetros tipado e snapshots
históricos de emissão continuam fora deste corte.

## Transporte dos consumidores

GET `/api/reports/consumers/stock/templates` ou `/consumers/session/templates`
lista revisões ativas publicadas cujo schema declara
`properties.contract.const` igual ao contrato do domínio. Basta permissão de
emissão e do domínio; não é necessário acessar rascunhos nem editar catálogo.
POST `/api/reports/consumers/stock/render` recebe template, version opcional,
parameters e material_id opcional. POST `/api/reports/consumers/session/render`
recebe template, version opcional, parameters, session_id e plant_id obrigatórios.
Ambos usam o token de sessão, aceitam format="html" (padrão) ou "pdf", devolvem HTML/no-store ou PDF inline/no-store e mensagens JSON
estruturadas em erro. Sem addon consumidor registrado, retornam 503 antes de
importar seu serviço. Não acrescentam dependência obrigatória ao manifesto.

Para emissão automática de PDF, passar format="pdf" explicitamente às funções
Python ou ao JSON da API. O runtime nativo continua necessário somente nessa
opção. Os templates/revisões existentes permanecem; nenhuma migration nova.
