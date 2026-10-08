# Componentes do addon

```mermaid
flowchart TD
 A[Workspace NiceAdmin] --> B[API autenticada]
 C[Addon consumidor] --> D[ReportTemplateService]
 B --> D
 D --> E[Catálogo SQLAlchemy]
 D --> F[ReportLayoutService]
 F --> G[ReportBindingService]
 D --> H[ReportPDFService]
 H --> I[Worker WeasyPrint]
```

ModuleManager descobre models e blueprints, aplica prefixos, cria tabelas novas segundo o fluxo vigente e sincroniza permissões/transações. Nenhuma alteração do Core foi necessária. Serviço de relatórios não importa ORM de outros addons. Chamadas internas também verificam RBAC; atualmente exigem contexto Flask/Login do servidor.
