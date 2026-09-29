# Limpeza de dados BrewStation e Estoque (SQLite)

Use `scripts/reset_brewstation_sqlite.py` para recomecar o cadastro de
receitas e materiais antes de importar novamente do Brewfather. SQLite nao
tem `TRUNCATE`; o script usa `DELETE` em uma transacao e **nao apaga as
tabelas nem o historico de migrations**.

1. Pare o Tesseract e qualquer processo que escreva no mesmo SQLite.
2. Confira o arquivo do banco configurado em `DATABASE_URL` (padrao de
   desenvolvimento: `instance/tesseract_dev.db`). Na raiz do projeto:

   ```powershell
   python .\scripts\reset_brewstation_sqlite.py .\instance\tesseract_dev.db
   ```

3. Confira as contagens impressas. Para executar a limpeza:

   ```powershell
   python .\scripts\reset_brewstation_sqlite.py .\instance\tesseract_dev.db --execute
   ```

O comando `--execute` cria uma copia consistente ao lado do banco, com o
sufixo `.backup-AAAAMMDD-HHMMSS-ffffff.sqlite`. Ele se recusa a executar
se detectar outra tabela com referencia a receitas ou materiais fora do
escopo. Se ocorrer, inspecione a dependencia citada antes de tentar de novo.
Falhas nas exclusoes revertem toda a transacao; o backup continua disponivel.

A limpeza inclui receitas manuais e importadas, ingredientes e de-para,
steps/historico, lotes e envases, especificacoes de malte/lupulo/levedura,
links e logs Brewfather, materiais e suas unidades, composicoes, compras,
cotacoes, movimentacoes e saldos. As regras de automacao permanecem, mas
perdem o vinculo com lotes apagados; seus logs de execucao sao removidos.

Permanecem usuarios, configuracoes, YeastBank (cepas e amostras), plantas,
dispositivos, fornecedores, fabricantes, categorias, origens, tipos de
produto, catalogo de unidades e a revisao do Alembic. A limpeza **nao**
altera receitas ou inventario dentro do Brewfather. Apos a operacao, cadastre
os materiais corretos e importe as receitas novamente; revise o de-para
antes de sincronizar saldos.
