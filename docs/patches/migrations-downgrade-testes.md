# Correção da suíte de migrations — 02/10/2026

## Diagnóstico e escopo

Retorno local: 498 testes aprovados, duas falhas e dois avisos de marca `slow`.
O upgrade real havia concluído; o teste encontrava dois heads falsos porque
seu regex só incluía revisões com aspas simples. A cadeia permanece intacta,
com head `e6274a913bc0`; nenhuma revisão de merge é necessária.

O downgrade falhava em `0d7080cf1fe8` porque a FK criada pelos models não
possuía o nome pressuposto pela revisão. A reprodução local também encontrou
falhas equivalentes posteriores em Categoria e YeastBank. O patch corrige:

- Leitura do grafo real pelo Alembic, com teste de aspas, annotations, merge
  e rejeição de múltiplos heads reais.
- Remoção por reflexão das FKs/uniques/índices das colunas retiradas, incluindo
  constraints sem nome no SQLite; demais referências são preservadas.
- Downgrades `0d7080cf1fe8`, `fd143ed5695c`, `0451604f9aad`, `f44a00fd711f`,
  `7faf3d2c92ca`, `27c13496373e`, `7b52062d7430` e `8b36e1f30843`.
- Remoção de índices redundante antes de excluir tabelas em `0d7080cf1fe8`,
  `6ddc874d16e7`, `0451604f9aad`, `f44a00fd711f` e `39c5bada7f65`.
- Recuperação de material/unidade/quantidade de ItemCotacao antes de remover
  o vínculo (oferta preenchida prevalece; oferta nula usa quantidade pedida).
  Vínculo órfão interrompe antes de modificar o schema.
- Recuperação do nome da Categoria a partir de descricao.
- Verificação das etapas preparatórias do teste de downgrade e registro da
  marca `slow` em `pytest.ini`, sem supressão de avisos.

Não modifica serviços de saldo/ledger, UI, modelos ou controllers gerados.
Não apaga banco/histórico nem executa `stamp`. O downgrade completo mantém
seu contrato de remover estruturas de revisões posteriores; não é backup nem
promessa de recuperar dados removidos por todas as revisões históricas.

## Aplicação e banco

```powershell
git -c gc.auto=0 am --keep-cr .\tesseract-migrations-downgrade-testes.patch
```

**Não exige novo `db upgrade`**: corrige testes/configuração e funções de
reversão nas revisões existentes, sem alterar IDs ou pais da cadeia.
A migration de envase 2A.2 continua necessária se ainda não foi aplicada.
Não executar downgrade no banco principal como etapa deste patch: os testes
abaixo criam seus próprios bancos temporários e só trabalham neles.

## Testes focados

```powershell
python -m pytest tests/test_migrations_idempotent.py tests/test_migration_schema_compat.py tests/test_migration_envase_request_key.py tests/test_migration_tipo_produto_legacy.py -q -W error::pytest.PytestUnknownMarkWarning
```

Verificar upgrade iniciado por `create_all` até o head, downgrade até
`091f87025ce4`, FKs nomeadas/sem nome, nomes alternativos de índices,
preservação de referências/dados restantes, quantidade nula/ofertada/zero,
interrupção por vínculo órfão, recuperação de categoria e ausência do aviso
`slow`. A suíte do TipoProduto continua cobrindo `nome`/`descricao` legado.

**Executado neste ambiente:** 13 passed em 9,99s, sem warnings, Python 3.12,
SQLAlchemy 2.0.51, Alembic 1.18.4 e SQLite em Linux. Isso inclui os comandos
Flask reais de upgrade/downgrade em subprocessos. A suíte completa de 500
casos não foi reexecutada aqui. Validar o comando focado no Windows antes de
considerar esta correção aprovada localmente.

Verificações adicionais da entrega: sintaxe Python, `git diff --check` e
aplicação por `git am --keep-cr` em checkout isolado da base com comparação
exata da árvore final.

## Rotas e continuidade

Não acrescenta ou altera rotas. Não há teste visual novo necessário.
O fluxo de envase continua em
`/brewstation/plant-workspace/<ID_PLANTA>?tab=sessions&session_id=<ID_SESSAO>`;
seu registro 2A.2 passou na seleção funcional informada pelo usuário.
Detalhes/estorno integrado (2B), precificação alinhada aos snapshots,
dashboards avançados e demais etapas continuam pendentes.

Referências técnicas: [batch e constraints sem nome](https://alembic.sqlalchemy.org/en/latest/batch.html#dropping-unnamed-or-named-foreign-key-constraints)
e [grafo de revisões](https://alembic.sqlalchemy.org/en/latest/api/script.html).
