# Casos de uso e RBAC

| Caso | Permissões |
|---|---|
| Abrir catálogo/workspace | report_templates.list |
| Ler revisão e solicitar prévia | report_templates.detail |
| Criar modelo | report_templates.create |
| Salvar rascunho | report_templates.update e report_templates.detail |
| Copiar revisão | report_templates.update |
| Publicar | report_templates.publish |
| Emitir revisão publicada | report_templates.render |

Permissões sincronizadas via anotações e mecanismo padrão do Core. Administrador tem permissões pelo contrato existente. Serviços rechecagem em processo; rotas não são a única proteção. Sem isolamento por organização: usuários autorizados acessam o catálogo compartilhado. Dados externos são fornecidos pelo chamador; não comprovam origem ou validade de negócio.

API de edição usa token de sessão X-Reports-CSRF disponibilizado pela tela /reports/ ou GET /api/reports/session após login. O endpoint de sessão fornece somente token, sem acesso ao catálogo, permitindo clientes com apenas permissão de emissão. Chamadas externas com autenticação independente ainda não têm contrato implementado; não contornar a proteção de sessão para anunciá-las como integração pronta.


## Evolução da IDE: blocos, condições e totais

| Caso | Permissões e comportamento |
|---|---|
| Listar blocos | report_templates.list; somente metadados ativos |
| Ler bloco para inserir cópia | report_templates.detail; gravação do destino exige update |
| Salvar seleção como bloco | report_templates.create e detail; origem persistida |
| Arquivar bloco | report_templates.delete; lock_version e confirmação; preserva inserções |
| Configurar condição ou total | report_templates.update e detail; somente rascunho |
| Conferir exibição e cálculos | report_templates.detail; prévia com dados e parâmetros válidos |

Totais não validam regras financeiras do domínio; consumidor fornece dados
normalizados. Condição não concede ou revoga permissão. Revisões publicadas
preservam condições/totais; mudar configuração exige nova revisão.
