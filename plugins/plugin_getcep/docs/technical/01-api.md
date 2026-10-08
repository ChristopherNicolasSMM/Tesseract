# GetCEP — plugin instalado em disco

Descoberta `plugins/plugin_*/plugin.json` + `plugin.py`, adicionada ao boot
após addons, antes de create_all. Manifesto type plugin, nome conforme pasta,
sem table_prefix/features; classe PluginBase sem register_models. Duplicidade
com módulo já carregado é erro. Plugins com requires não vazio são recusados:
resolução de dependências versionadas/ativação/desativação seletiva não está
implementada por este pacote. GetCEP tem requires vazio. O padrão de registro
dos addons existentes não foi alterado; não interpretar o loader como entrega
de todo o gerenciador de plugins proposto nas skills.

GET `/api/plugins/getcep/<cep>` exige login; endereço é dado auxiliar público,
não requer admin. Sucesso: `success`, `address` (cep normalizado, logradouro,
bairro, cidade, estado), `source=ViaCEP`. CEP malformado 422; ausente 404;
falha externa, resposta divergente/malformada, timeout ou redirect 503.
Asset local `/api/plugins/getcep/assets/getcep.js`; base Core só o inclui quando
plugin registra o context processor. Não altera arquivos gerados do CrudGen.

ViaCEP: HTTPS host fixo, CEP estrito no caminho, sem redirects/URLs externas;
requests já existente, sem upgrade/adicional. Timeouts conexão 2s/leitura 3s,
stream máximo 16KiB; JSON/schema/CEP/cidade/UF validados. Não envia CNPJ/CPF,
contatos ou endereço digitado: só o CEP consultado. Cache em memória por app,
sucesso TTL 1h, máximo 256 entradas, proteção por Lock, cópias nas respostas.
Falhas não ficam em cache; processos têm caches independentes. Timeout de
leitura não constitui prazo total; cliente aborta em 10s, sem travar o form.
Não é serviço de validação cadastral nem prova de entrega postal.

JS delegado: MutationObserver inclui formulários AJAX; escopo é form ou
`data-address-scope`. Formulário com múltiplos endereços deve declarar um
escopo por endereço. São suportados os nomes canônicos cep/logradouro/bairro/
cidade/estado usados no cadastro real e o mapeamento explícito endereco_cep/
endereco_rua/endereco_bairro/endereco_cidade/endereco_uf dos campos Core User.
O perfil Core atual não exibe esses campos de endereço no formulário: o
mapeamento não significa entrega de uma tela adicional de endereço pessoal. Campos com outros nomes exigem mapear
explicitamente a integração, sem suposição por labels traduzidas.
Número/complemento não vêm da resposta. Sequência + AbortController + comparação
do CEP impedem respostas atrasadas. Só campo vazio e ainda igual ao momento
da consulta recebe preenchimento, por value/textContent (sem HTML remoto).
Consulta não escreve no banco nem transforma sucesso da API em requisito de save.

Testes Python usam transporte simulado (timeout, redirects, payload inválido,
404, cache/expiração/limite). Testes Node executam o JS real com DOM mínimo e
rede controlada, sem reproduzir CSS/Bootstrap/navegador completo. Consulta real,
contraste do tema e usabilidade no browser instalado exigem conferência local.
Fonte: [ViaCEP](https://viacep.com.br/), consultada em 07/10/2026.


## Correções de carregamento — 08/10/2026

Asset canônico `/plugins/getcep/static/getcep.js?v=1.0.1`, fora de `/api`, com
MIME JavaScript e versão para renovar cache. A rota antiga do asset permanece
compatível. Context processor fornece getcep_lookup_url por url_for, incorporando
SCRIPT_NAME; base envia data-getcep-url ao script. Não concatenar raiz `/api`
quando aplicação está montada sob prefixo. Endpoint/provider de consulta continuam
iguais; não houve alteração de timeout/cache/validação no provedor.

UI tem controles/estado explícitos no template manual de organização, reutilizados
pelo JS sem duplicação. Formulários canônicos do Estoque continuam atendidos por
attachment delegado, inclusive AJAX. Inicialização aguarda DOMContentLoaded quando
necessário e também tenta attach em focusin. Consulta por pausa de 450ms só quando
formato completo; blur/clique cancelam debounce. Cada timeout guarda seu próprio
AbortController, sem abortar consulta mais nova. JSON inesperado, sessão encerrada,
CEP ausente e falha são mensagens visíveis, sem limpar campos existentes.
Estilo usa text-muted, já tratado pelo tema escuro do Tesseract.

Teste complementar executa Chromium real com HTML/assets despachados pelo
Flask test_client em SQLite memória, através de interceptação Playwright.
Não é DOM mínimo: scripts, formulários nativos, CSS, preferência real de tema
e navegação são executados no browser. ViaCEP é simulado nesse teste. Validação
no navegador/servidor instalado permanece local; teste não certifica proxy do usuário.
