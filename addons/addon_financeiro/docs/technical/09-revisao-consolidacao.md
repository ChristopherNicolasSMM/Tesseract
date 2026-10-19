# Revisão pontual após as três entregas de consolidação

Base: `eb50410`. Addon Financeiro: `1.7.1`. Sem alteração de schema ou dependências.

| Achado | Ajuste | Validação |
| --- | --- | --- |
| `results.panel` consultava categorias, centros, classificações e histórico de apropriações para todas as visões | Carregamento condicionado à visão, com histórico paginado apenas em Apropriações e Fechamento | Custos e Apropriações abrem mesmo com mais de 2.000 categorias sem relação com a consulta; ausência de contagem do histórico de apropriações nas outras visões |
| Atalho de dashboard era excluído também das subvisões de Resultados | Inclusão do dashboard no menu da área de Resultados | Navegação acessível em todas as visões dessa área |
| Visões sem apuração temporal não validavam datas do cabeçalho | Validação do contexto também em revisão, custos, fechamento, classificações e apropriações | Resposta 422 a datas inválidas e recuperação com contexto válido |
| Conferência carregava a integração de estoque duas vezes | Reutiliza disponibilidade já apurada na revisão | Regressões de conferência e fechamento |
| Histórico exibia checksum, sem compará-lo ao snapshot | Recalcula SHA-256 do JSON canônico e adiciona `integrity.valid` e `integrity.calculated_digest` | Snapshot ou checksum alterados diretamente no banco geram divergência visível sem reescrita |
| Consulta do fechamento dependia da tela HTML | Leitura pública por DTO, com organização explícita e exportação na própria tela | Organização diferente retorna 404; leitura sem permissão retorna 403; somente SELECT na exportação |

GET `/api/financeiro/results/closures/<id>?organization_code=A` exige autenticação e `financial_results.list`. Apenas `organization_code` é aceito como query string. Retorna `success` e `item`, com snapshot original, metadados, situação atual da versão e conferência do checksum. O cabeçalho é `Cache-Control: no-store`. Registro ausente na organização retorna 404; entrada inválida retorna 422. Organizações inativas continuam consultáveis.

O SHA-256 cobre somente o snapshot canônico, conforme o contrato da entrega 3. Metadados externos ao snapshot e evento de reabertura são retornados separadamente. Não há assinatura digital, recalculo de checksum armazenado, reconstrução de resultado histórico por consulta atual ou alteração das regras de reconhecimento/fechamento.

Os limites de segurança das consultas permanecem explícitos. Esta revisão remove dependências indevidas entre telas; não elimina os limites do demonstrativo, revisão de origens ou integração de estoque.
