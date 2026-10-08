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
