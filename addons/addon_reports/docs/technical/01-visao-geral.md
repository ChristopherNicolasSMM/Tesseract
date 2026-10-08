# Relatórios — visão geral

Construção iniciada sobre main/fae21ed1ffe8ed110d2f561e64fc8e2b1221200e e reaplicada
sobre origin/main/6b9b75f (Financeiro/Organização/GetCEP), sem conflitos.
Pacote consolidado autorizado para entrega; sem envio ao remoto. Data: 08/10/2026.
Roteiro de aplicação em `docs/patches/reports-mvp-ide-integracao.md`.

Implementado: addon descoberto pelo ModuleManager, tabelas de modelo/revisão/parâmetro, RBAC do Core, workspace /reports/, dados de exemplo, contrato JSON Schema, edição otimista, publicação imutável via serviço, cópia de revisões, composição declarativa HTML, impressão pelo navegador e PDF opcional em subprocesso. Capacidade pública HTTP: /api/reports/render; serviço Python exige contexto de usuário autorizado. O catálogo é compartilhado entre usuários com permissões; Organização do Core não é tenant.

O primeiro corte inclui IDE de texto/tabela/divisor, carregamento de exemplos,
publicação, prévia, integração contextual de Estoque/BrewStation e migration.
Percursos reais de navegador e temas foram exercitados. A entrega ainda depende
da geração/conferência do patch e validação local do usuário. Assets, blocos
reutilizáveis, estilos editáveis, condições, fila, histórico de emissões e
registro de componentes no banco permanecem planejados.

Referências reais de UI: templates/core/base.html, templates/core/freestyle/model_minimal.html, model_full.html, model_abas.html; organização da documentação em docs/skills/04; controles e anotações do CrudGen; diálogos/toasts em docs/skills/15. Não se reutiliza o Designer removido descrito como histórico em docs/skills/16.

Backend e impressão funcionam independentemente do tema da IDE. Conteúdo recebido não é interpretado como Python, Jinja ou HTML. O primeiro compilador usa renderers confiáveis declarativos; edição HTML/Jinja avançada ficará para fase separada e não é oferecida neste corte.

Leia [fluxos](03-fluxos.md), [persistência](04-modelo-de-dados.md), [operação](06-manutencao-e-expansao.md), [estado de validação](07-validacao-e-pendencias.md) e [integração dos consumidores](08-integracao-consumidores.md).
