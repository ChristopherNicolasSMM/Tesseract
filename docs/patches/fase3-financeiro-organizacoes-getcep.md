# Fase 3 — financeiro inicial, organizações e GetCEP

Entrega inicial disponibilizada; a conferência local do usuário apontou
problemas de CEP, preservação de formulário e padrões de telas/menu. Não
considerar esta entrega funcionalmente validada. Correção em
[fase3-financeiro-cadastro-getcep-correcao.md](fase3-financeiro-cadastro-getcep-correcao.md). Base cad5115 (organizações Core), cujo conteúdo
foi aplicado/validado pelo usuário e já tem a primeira organização criada.
Hashes locais podem diferir após git am: compare conteúdo, não só hash.

## Proposta concretizada neste único pacote

| Parte | Evidência e impacto | Dependência/migration | Critério de conclusão |
|---|---|---|---|
| Dados empresariais | Organization antes só tinha identidade; novo perfil legal/contato/endereço principal opcional | Core existente; b82d9e43a017 | Organização atual mantém ID/código, campos válidos podem ser salvos; CNPJ canônico único |
| Responsáveis | Novo cadastro Core com nome/função/CPF/contato/ativo; sem usuários/RBAC automáticos | Organization; mesma migration | Criar/editar/inativar; impedir edição por outra organização e por usuário sem admin |
| Financeiro inicial | Novo addon com catálogo, política explícita e Decimal público; estoque ainda global | Organização ativa + moeda cadastrada; mesma migration | Sem moedas/políticas implícitas; configuração inicial única, imutável; sem float e efeitos no estoque |
| DocumentValidator | Core tinha CPF/CEP permissivos e não CNPJ; classe compartilhada e exportada pelo addon | Sem rede/dependência nova | CPF/CNPJ numérico/alfanumérico/CEP normalizados; caracteres inválidos e DV incorreto rejeitados |
| GetCEP | PluginBase existia, mas faltava descoberta no boot; plugin sem tabelas + script compartilhado | requests já instalado; sem migration própria | Erros não apagam dados; preenchimento só vazio, sem respostas antigas; alcance nos forms reais de organização/Estoque |
| Reconciliação | Relatório de organizações ainda dizia pendente | Confirmação do usuário | Marcar só essa entrega como aplicada/validada; não presumir validações anteriores não confirmadas |

Detalhes, APIs e limitações:
[Financeiro](../../addons/addon_financeiro/docs/technical/01-contratos.md),
[manual](../../addons/addon_financeiro/docs/manual/01-configuracao.md),
[GetCEP](../../plugins/plugin_getcep/docs/technical/01-api.md).
Nenhum arquivo gerado do CrudGen foi editado. Sem upgrades de dependências.
`docs/imgs/logo.png` alheio ao pacote foi excluído da seleção.

## Aplicação em PowerShell

Parar a aplicação durante a atualização; no checkout que já recebeu organizações:

```powershell
git -c gc.auto=0 am --keep-cr .\tesseract-fase3-financeiro-organizacoes-getcep.patch
python run.py db upgrade
```

`flask db upgrade` é equivalente usando o mesmo ambiente/configuração Flask
habitual. Exige migration **b82d9e43a017**, parent a71c8d32f906. Reinicie a
aplicação depois do upgrade. Não basta create_all: ele não adiciona as colunas
novas à organização já existente. Nenhum dado antigo recebe moeda ou vínculo.
Downgrade é bloqueado quando há perfil/responsáveis/moedas/políticas, preservando
cadastro; não é procedimento de estorno. Migrations online SQLite verificadas;
PostgreSQL, Windows e reprodução integral das versões fixadas não certificadas.

## Roteiro visual local

Use o host/porta da instalação; exemplos abaixo para `http://localhost:5000`.

1. `/admin/organizations/`: confirme o ID e código da empresa criada; preencha
   razão social/nome fantasia/CNPJ/inscrições/contato. Salve e recarregue.
   CNPJ inválido deve mostrar erro; máscara válida vira código canônico.
2. Informe `01001-000` num endereço vazio, saia do campo ou consulte pelo botão:
   ViaCEP deve sugerir Praça da Sé, Sé, São Paulo/SP. Preencha número/complemento.
   Troque CEP com endereço já preenchido e confira que os valores são preservados.
   Sem internet, preencha e salve manualmente.
3. Abra Responsáveis; adicione nome/função, contato e CPF opcional. Edite/inative.
   Responsável não aparece como usuário nem recebe permissões por esse cadastro.
4. `/financeiro/`: confirme catálogo vazio na primeira visita. Cadastre a moeda
   deliberada, por exemplo BRL/Real/2, selecione organização/moeda/arredondamento.
   Confira a política. Uma segunda configuração inicial da mesma organização
   deve dar conflito, sem alterar a original. Escolha não tem default silencioso.
5. `/estoque/enderecos/`: abra formulário novo e edição/modal. Confira botão CEP,
   número/complemento manuais, contraste no tema claro/escuro e preservação de
   dados em falha. Campos introduzidos por AJAX devem receber o mesmo controle.
6. Usuário comum: Financeiro/admin organizações deve ser 403; auxiliar CEP exige
   login. Confira menu Financeiro/Configuração financeira para administrador.

Conferência visual humana e consulta ViaCEP a partir do servidor instalado
permanecem locais. Automação testou templates/JS, não hardware/navegador real.

## Testes e evidências de geração

Runtime: Python 3.12.3, Flask 3.1.3, Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.51,
pytest 9.1.1. Alembic disponível 1.20.0, diferente do requirements fixado 1.18.4;
esta entrega não certifica reprodução integral das dependências.

Prefixo de todos os comandos Python desta validação:
`PYTHONPATH=/workspace/scratch/af6b56a6223b/venv-yeast-audit/lib/python3.12/site-packages /usr/bin/python3`.

- `-m pytest tests/test_core_organizations.py -q -W error::sqlalchemy.exc.LegacyAPIWarning`:
  **33 passed in 34.23s**, antes da regressão consolidada.
- `-m pytest tests/test_financeiro_foundation.py tests/test_core_organizations.py tests/test_migrations_idempotent.py tests/test_migration_schema_compat.py tests/test_phase5_module_manager.py tests/test_module_discovery.py -q -W error::sqlalchemy.exc.LegacyAPIWarning`:
  **130 passed in 84.98s** (74 novos + 56 existentes). Inclui cadeia real
  create_all + flask db upgrade desde baseline e downgrade no banco vazio,
  migração de organização já povoada, rollback e guards contra perda de dados.
- `-m pytest tests/test_phase2_rbac.py tests/test_phase7a_transactions.py tests/test_menu_hierarquico.py tests/test_menu_grouped_by_feature.py tests/test_admin_smart_list_parity.py -q -W error::sqlalchemy.exc.LegacyAPIWarning`:
  **98 passed, 2 failed in 119.44s**. Não declarar a seleção toda aprovada.
- Reexecução final dos 74 testes novos após ajustes de validação/metadata:
  **74 passed in 33.90s**.
- `node --check plugins/plugin_getcep/static/getcep.js`: exit 0.
- `node tests/test_getcep_ui.cjs`: **6 cenários aprovados**, executando o script
  real com DOM mínimo/rede simulada: preenchimento preservado, resposta antiga,
  falha, formato/país, país alterado durante consulta e nomes endereco_* do Core. Não é teste visual real.

Total distinto das seleções Python: **228 aprovados e 2 falhas preexistentes**.
As consultas HTTP do GetCEP nos testes são simuladas, sem chamadas em massa.
Não houve execução de testes do financeiro em banco de produção/instalado.

### Falhas reproduzidas sem o pacote (base cad5115)

Comando executado no checkout de organizações anterior:

```bash
PYTHONPATH=/workspace/scratch/af6b56a6223b/venv-yeast-audit/lib/python3.12/site-packages /usr/bin/python3 -m pytest tests/test_menu_grouped_by_feature.py::test_grupo_automacao_tem_2_transacoes tests/test_menu_grouped_by_feature.py::test_de_para_de_ingredientes_agora_fica_em_ingredientes -q --tb=short --show-capture=no -W error::sqlalchemy.exc.LegacyAPIWarning
```

Resultado: **2 failed in 3.12s**, mesmos testes/erros:

```text
test_grupo_automacao_tem_2_transacoes:
E   assert 3 == 2

test_de_para_de_ingredientes_agora_fica_em_ingredientes:
E   sqlalchemy.exc.LegacyAPIWarning: The Query.get() method is considered legacy as of the 1.x series of SQLAlchemy and becomes a legacy construct in 2.0.
```

Teste de contagem precisa reconciliar as três entradas já existentes no catálogo
mash_control; Query.get está no próprio teste. Registrados como pendências de
qualidade, sem incluir alteração do menu BrewStation neste pacote financeiro.

## Ordem recomendada após validação deste pacote

| Ordem | Pacote coerente | Situação/decisões | Migration | Conclusão esperada |
|---|---|---|---|---|
| 2 | Versões de política, taxas e conversão pública | Proposto; definir precisão de taxa, tipos/fontes e vigência, mudanças de base com operação existente | Sim | Par e direção explícitos, taxa positiva, data/fonte, valor original/convertido e snapshot; sem câmbio automático/paridade |
| 3 | Contexto organizacional de compras/estoque | Exige decisão de propriedade de material/saldo e tratamento do legado; estoque hoje global | Sim | Sem misturar bases/organizações; vínculos explícitos e ledger central |
| 4 | Cotação/pedido/recebimento com moeda e custos | Depende dos contratos anteriores; conferir concorrência, snapshots e recebimento parcial | Sim | Custo médio recebe somente montante convertido validado; atomicidade/rollback/idempotência |
| 5 | Títulos a pagar/receber, contas e liquidações | Proposto; decidir escopo operacional, categorias, permissões e conciliação | Sim | Pagamentos parciais, taxas/diferenças cambiais e histórico sem recalcular estoque |
| Paralelo | Qualidade/documentação/temas | Duas falhas antigas de testes comprovadas; PostgreSQL/Windows/dep. fixadas e contraste exigem verificação | Conforme correção | Evidência proporcional, estados implementado/validado/proposto distintos |

Múltiplos endereços por organização (hoje principal único), cadastro bancário,
auditoria de autoria, versões de dados legais e validação cadastral Receita
ficam propostas, sem compromisso fiscal assumido por este patch. YeastBank
físico e PID/hardware continuam nas frentes anteriores; não foram reabertos.


## Empacotamento e aplicação isolada

Gerado por `git format-patch -1 --stdout`, sobre cad5115; aplicado por
`git -c gc.auto=0 am --keep-cr` em worktree isolado da mesma base.
Reexecução da seleção principal nesse checkout: **130 passed in 85.64s**.
Os arquivos Python da seleção permaneceram iguais após esta execução;
o ajuste final do mapeamento JS foi validado pelos 6 cenários Node.
Árvores do commit de geração e commit aplicado comparadas por rev-parse;
`git apply --reverse --check` e `git diff --check` aprovados. A revisão final
de documentação/JS também passou por nova aplicação isolada, comparação de
árvores, Node e verificação reversa antes da disponibilização.
A aplicação local do usuário e conferência visual permanecem pendentes.
