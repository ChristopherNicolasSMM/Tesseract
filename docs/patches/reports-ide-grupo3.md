# Reports — IDE, grupo 3 (etapas 7–9)

Patch incremental sobre main d4dd0e8c85da066fc0a1784e241551c3f18491eb,
que já contém os grupos 1–2 e as entregas recentes de compras/estoque.
Preserva essas entregas. Não reaplicar patches anteriores de relatórios.
Repositório: https://github.com/ChristopherNicolasSMM/Tesseract .

## Aplicação

Use a branch com o main citado (ou descendente compatível) e árvore limpa.
Confira git status e sincronize seu main antes de aplicar. Se git pull
--ff-only apontar divergência, resolva a integração dos commits locais antes
desta aplicação; não use reset para descartar trabalho. Faça backup do banco
antes do upgrade e reinicie a aplicação ao concluir.

```powershell
git am --keep-cr .\tesseract-reports-ide-grupo3.patch
python run.py db upgrade
python -m pytest tests/test_reports_bindings.py tests/test_reports_blocks.py tests/test_reports_blocks_migration.py tests/test_reports_calculations.py tests/test_reports_composition.py tests/test_reports_consumers.py tests/test_reports_delivery.py tests/test_reports_formats.py tests/test_reports_images.py tests/test_reports_pagination.py tests/test_reports_sections.py tests/test_reports_styles.py tests/test_reports_workspace.py -q
node --test tests/browser/reports_layout.test.cjs tests/browser/reports_history.test.cjs
```

Recarregue http://localhost:5000/reports/ após reiniciar. Não acrescenta
requisitos Python/JS de produção. Pillow da entrega anterior permanece;
HTML/impressão pelo navegador não exigem MSI/Pango. WeasyPrint é opcional.
Playwright é ferramenta de desenvolvimento; não precisa instalá-lo para usar
a IDE. Os testes Node requerem Node somente para a verificação JavaScript.

## Migration

e59f6ab8d704 sucede b48d5e09a673 (cadastro monetário de compras) e cria
somente tesseract_reports_report_block. Um único head foi conferido. A revisão
valida tabela compatível eventualmente criada pelo boot e preserva registros.
Schema incompatível causa erro explícito, sem adaptação destrutiva automática.
Não usar stamp para pular verificações; não alterar tabelas manualmente.
Downgrade desta revisão remove o catálogo, portanto exige backup. Ele não
apaga cópias inseridas em templates, que são valores do layout da revisão.

## O que está incluído

- Blocos: salvar seleção persistida, inserir cópia com IDs novos, arquivar
  com controle otimista. Chave única continua reservada após arquivamento.
- Condições: comparar campo dos dados/parâmetros com scalar tipado eq/ne;
  canvas mantém conteúdo, prévia e impressão aplicam a condição.
- Totais: sum/avg/min/max/count por coluna, cálculo decimal antes do formato,
  rodapé único após linhas. Null é ignorado nas operações numéricas; count
  inclui todas as linhas; coleção vazia produz soma/count zero e outros null.
- Produtividade: desfazer/refazer em memória, 30 estados/8 MiB, atalhos de
  salvar e histórico. Salvar/trocar revisão/recarregar reinicia o histórico.
- RBAC, CSRF, contratos tipados, imutabilidade publicada, dark/light e folha
  branca na impressão. Manual, fluxos, casos de uso e detalhes atualizados.

## Conferência manual

1. Abra um rascunho, monte uma seção com textos e salve-a como bloco.
2. Insira o bloco em outro rascunho, edite a cópia e confira que a origem não
   muda. Dados, contratos e definições de parâmetros não são importados:
   adapte os vínculos e confira a prévia antes de publicar.
3. Arquive o bloco com confirmação; confira que cópias existentes permanecem.
4. Adicione parâmetro booleano e configure condição igual a verdadeiro num
   texto ou seção. Teste falso/verdadeiro na prévia; nulo, zero e falso são
   diferentes. Campo ausente gera erro, condição não controla autorização.
5. Configure total numa coluna numérica/moeda. Teste zero, null e tabela
   vazia; média ignora null e contagem inclui linhas com null.
6. Faça alterações em conteúdo/propriedades/página e use desfazer/refazer.
   Edite depois de desfazer para descartar redo. Ctrl+S salva e limpa histórico.
   Dentro de campos, Ctrl+Z mantém o desfazer de digitação do navegador.
7. Salve/reabra, publique e clone; confira configuração preservada e controles
   de edição bloqueados na revisão publicada. Catálogo pode capturar seleção
   publicada; inserir depende de rascunho.
8. Alterne os temas. Prévia escura usa papel #273549; impressão branca.
   Confira paginação no diálogo local, incluindo total da tabela uma vez.

Histórico não desfaz criação/publicação/arquivamento remoto nem recupera sessões
anteriores. Condições não aceitam expressão livre, AND/OR ou filtro de linhas.
Totais não convertem moedas/unidades: consumidor deve normalizar seus dados.
Prévia continua HTML contínuo; o total pode ir para a próxima folha quando não
cabe. Condição falsa pula a resolução dos descendentes, mas valida sua estrutura;
teste também os parâmetros que tornam o conteúdo visível.

## Evidência e limites

203 testes Python e 10 subtestes; um PDF WeasyPrint opt-in desabilitado.
11 testes Node. Percurso Playwright 1.51.1/Chromium 134 aprovado na base atual,
incluindo histórico, blocos, condições, totais e regressões de consumidores.
Migration exercitada em SQLite vazio, tabela compatível preservada, schema
incompatível rejeitado e tabela real criada pelo ModuleManager aceita.
Não foi executada migration PostgreSQL/Windows nem PDF servidor WeasyPrint.

PDF Chromium com 100 linhas e total único 5.000,0: 10 folhas A5 paisagem e
cinco A4 retrato, incluindo fechamento separado. Na etapa 8, total, conteúdo
e numeração conferidos por extração/renderização Poppler; prévia escura também
inspecionada. Diálogo de impressão e aplicação Windows dependem da validação
local. A verificação git am em checkout isolado acompanha a entrega final.

Aplicação git am --keep-cr conferida em checkout isolado do main citado,
sem conflitos; árvore idêntica à implementação. A suíte Python/Node passou
no checkout aplicado. Conferência reversa do patch também sem erros.
