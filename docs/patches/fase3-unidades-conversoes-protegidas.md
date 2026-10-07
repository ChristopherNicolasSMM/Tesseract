# Fase 3 — unidades e conversões protegidas

Implementado e testado no ambiente de geração. Aplicação/validação local deste
pacote ainda pendentes. O pacote anterior de compras/recebimento foi aplicado e
validado pelo usuário, incluindo os testes. Base de geração: a616fcf; hashes
locais podem diferir após git am. Sem migration ou upgrade de dependências.

## Evidências e solução

Seis casos novos executados sobre a base anterior falharam (6 failed in 7.46s):
fator infinito aceito; base KG trocada com saldo; conversão transferida de
material; lixeira de conversão usada; código duplicado; base usada desativada.
A solução fica em hooks e serviços manuais. O template CrudGen ganhou um hook
para inativação em lote; apenas Material e MaterialUnidade foram regenerados.

Fatores devem ser positivos e finitos; base exige 1. Código é normalizado e
validado no catálogo; não pode duplicar conversão não arquivada. PCT continua
código; conteúdo é fator do material. ITEM/UN exigem conversão explícita.
Qualquer uso declarado do material congela alterações semânticas das
conversões existentes, incluindo tipo de uso e ativação. Nova conversão
explícita pode ser adicionada preservando a base. Não há versionamento de
fatores em uso neste pacote.

Trocar base exige ausência de uso e de outras conversões, inclusive arquivadas.
Não se desmarca a base isoladamente. Cadastro explícito da mesma base legada
conhecida é permitido sem alterar saldo; base desconhecida com histórico não é
inferida. Material com conversões/referências não pode desaparecer pela lixeira
ou exclusão; inativação permanece disponível. Restauração verifica pai, código,
fator e compatibilidade da base. Exclusão permanente exige registro arquivado.

A reserva transacional da linha Material é compartilhada com a movimentação
central. Cadastro público de conversões usa a mesma reserva/validação. Erros
revertem fator, espelho da base e arquivamento; snapshots, custos e ledger não
são recalculados. Inativação em lote mantém resultado por item do contrato
existente, sem prometer atomicidade do lote inteiro.

Core consulta referências fracas declaradas em modelos carregados e tabelas
existentes, incluindo arquivados. Não importa modelos BrewStation no Estoque.
Não varre referências guardadas em JSON, módulos não carregados ou escritores
externos. Concorrência é verificada em SQLite; PostgreSQL não foi certificado.
RFQ, recebimento parcial e versionamento econômico de fatores ficam fora.

## Aplicação e conferência

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-fase3-unidades-conversoes-protegidas.patch
```

Não é necessário `flask db upgrade` para este pacote. Migrations já instaladas
continuam pré-requisito da aplicação; testes usam schema sintético, sem atestar
migração do banco instalado.

1. Em `/estoque/materials`, crie material de teste sem referências e configure
   base e conversão em `/estoque/material-unidades/`. Confira fator válido e
   bloqueio de zero/infinito, duplicata e transferência para outro material.
2. Em `/estoque/material-unidades/<ID>`, corrija fator antes do uso. Adicione
   saldo pelo fluxo normal de estoque e tente alterar fator, base, inativar e
   arquivar. Deve haver erro amigável, com valores preservados.
3. Adicione outra conversão explícita mantendo base; confirme que saldo e
   ledger anteriores não mudaram. Use PCT com fator do próprio material.
4. Em material sem uso, confira lixeira/restauração: base com outras conversões
   não arquiva; código conflitante bloqueia restauração. Material pai com
   conversões também não arquiva. Use registros descartáveis para exclusão.
5. No workspace `/brewstation/plant-workspace/<ID>?tab=recipe&recipe_id=<ID>`,
   confira prévia e confirmação de conversão de ingrediente. Repita em temas
   claro/escuro. Conferência visual humana permanece pendente; testes cobrem
   respostas de API/formulário e contrato JavaScript.

## Próximos pacotes

Revisão pontual de Query.get/LegacyAPIWarning e contratos de migrations pode
avançar sem upgrade amplo. Moedas/câmbio exigem decisão sobre moeda-base,
precisão e fonte/data; nenhuma conversão automática ou paridade foi adicionada.
YeastBank físico exige contrato de unidade, genealogia, consumo e estorno.
Hardware real e proveniência de eventos requerem validação própria.

## Verificações reproduzíveis

Runtime: Python 3.12.3, Flask 3.1.3, Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.51,
pytest 9.1.1. Dependências mantidas. Com o ambiente do projeto ativado:

```powershell
python -m pytest tests/test_material_unit_integrity.py tests/test_addon_estoque.py tests/test_purchase_integrity.py -q --tb=short --show-capture=no
python -m pytest tests/test_mash_control_ingredient_resolution.py tests/test_feature_envase.py tests/test_precificacao_envase.py tests/test_phase4_crudgen.py -q --tb=short --show-capture=no
node tests/js/test_workspace_ingredient_conversion.cjs
```

O ambiente de geração executou `/usr/bin/python3 -m pytest` com
`PYTHONPATH=/workspace/scratch/af6b56a6223b/venv-yeast-audit/lib/python3.12/site-packages`.
Os casos novos incluem concorrência CRUD/CRUD e CRUD/cadastro público,
concorrência de primeira movimentação com troca de base, referências de receita
inclusive arquivadas, erros de API/formulário e rollback induzido de gravação.

Resultados finais no ambiente de geração:
- Unidades (38), estoque (151) e compras (39): **228 passed in 287.18s**.
- Ingredientes, envase, precificação e CrudGen: **191 passed in 211.51s**.
- Total: **419 casos distintos aprovados** nas duas seleções.
- JavaScript: prévia, confirmação, cancelamento, erro, contexto e envio único aprovados.
- Dois serviços regenerados: igualdade byte a byte com o template aprovada.
- `git diff --check`: aprovado. Patch produzido com `git format-patch`; protocolo
  de entrega exige `git am` em checkout isolado na base a616fcf, igualdade das
  árvores e `git apply --reverse --check` antes de disponibilizar o arquivo.
