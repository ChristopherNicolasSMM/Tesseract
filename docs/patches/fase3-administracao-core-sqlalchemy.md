# Fase 3 — depreciações nas telas administrativas Core

Aplicado pelo usuário. Validação dos testes locais ainda pendente de confirmação.
Base cad38cd, após compatibilidade do Alembic/API de usuários. Os pacotes de
unidades/conversões e compatibilidade anteriores continuam com validação local
pendente de confirmação; a solicitação para continuar autoriza este trabalho.
Sem migration, alteração de modelos, dependências ou arquivos CrudGen gerados.

## Evidência e escopo

Reprodução na base: quatro testes com LegacyAPIWarning como erro, quatro falhas
em 6.77s. Uma em cada controller manual: edição de usuário, associação de
permissões ao Role, edição de transação manual e desativação de regra de campo.
Erro em todos:

```text
sqlalchemy.exc.LegacyAPIWarning: The Query.get() method is considered legacy as of the 1.x series of SQLAlchemy and becomes a legacy construct in 2.0. The method is now available as Session.get()
```

São avisos de compatibilidade no funcionamento normal atual; tornam-se falhas
quando tratados como erro. Não foram apresentados como falhas de produção
sob a configuração padrão. O objetivo é remover a API legada nos fluxos manuais
administrativos sem alterar seus contratos.

| Área | Acessos substituídos | Contratos preservados |
| --- | --- | --- |
| Usuários | 6: detalhe, edição, ativação/desativação, reset, roles | Validação do payload, senha existente, atribuições, proteção da autodesativação HTML |
| Roles | 4: detalhe, edição, permissões, exclusão | Permissões vindas do catálogo, nomes únicos, bloqueio de exclusão com usuários |
| Transações | 5: edição, promoção, rebaixamento, toggle, exclusão | Catálogo do código protegido, hierarquia e referências, operações manuais |
| Regras de campo | 2: toggle e exclusão | Catálogo e validações existentes, regras ativas/inativas |

Os 17 acessos usam db.session.get mantendo contexto da sessão, retorno None
para ID ausente e os mesmos decorators, redirects, flashes e commits.
Vinte leituras legadas nos testes correspondentes também foram atualizadas.
Os controllers são manuais; nenhum template ou arquivo gerado foi editado.

Os testes novos verificam redirects para IDs inexistentes nas 17 operações e
permissão administrativa em quatro áreas. Os casos de ID ausente verificam
que o cadastro de usuários permanece idêntico. As suites existentes conferem
persistência, referências, hierarquia, senha, roles e parâmetros de regras.

## Reprodução e aplicação

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-fase3-administracao-core-sqlalchemy.patch
python -m pytest tests/test_admin_users_pages.py tests/test_theme_profile_roles_versioning.py tests/test_ui_navigation_fixes.py tests/test_menu_hierarquico.py tests/test_phase7b_rules_engine.py tests/test_phase7a_transactions.py tests/test_admin_core_lookup_contracts.py -q -W error::sqlalchemy.exc.LegacyAPIWarning --tb=short
python -m pytest tests/test_admin_smart_list_parity.py tests/test_phase2_rbac.py -q -W error::sqlalchemy.exc.LegacyAPIWarning --tb=short
```

Aplicar após o pacote de compatibilidade de migrations. Não requer
`flask db upgrade`. Reiniciar a aplicação após aplicar. Ambiente de geração:
Python 3.12.3 com `/usr/bin/python3`; PYTHONPATH apontando para
`/workspace/scratch/af6b56a6223b/venv-yeast-audit/lib/python3.12/site-packages`.
Flask 3.1.3, Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.51 e pytest 9.1.1.
As diferenças transitivas/Alembic registradas no pacote anterior continuam;
não se certifica reprodução integral de requirements.txt nem PostgreSQL.

## Conferência visual

Não há mudança de layout ou de seletores. Como administrador, conferir:

1. `/admin/users/`: abrir usuário descartável, editar dados, atribuir Role e
   redefinir senha; confirmar bloqueio de autodesativação na tela.
2. `/admin/roles/`: conferir seleção de permissões em Role descartável e
   bloqueio de exclusão de Role ainda atribuído a um usuário.
3. `/admin/transactions/`: conferir menu manual descartável, promoção e
   rebaixamento; uma transação do código mantém proteção de edição/exclusão.
4. `/admin/field-rules/`: conferir ativação/desativação em regra descartável;
   usar material de teste para conferir efeito da validação existente.
5. Em usuário comum, conferir bloqueio de acesso às quatro telas. Repetir
   conferência de apresentação nos temas claro/escuro se desejado.

Testes usam bancos sintéticos; conferência visual humana permanece pendente.
Não excluir dados usados apenas para executar o roteiro.

## Pendências preservadas

| Frente | Evidência / natureza | Prioridade e dependência | Migration | Critério de conclusão |
| --- | --- | --- | --- | --- |
| Outros lookups Core | Ainda há Query.get em OData, Designer, Model Builder e provider OData; fora deste conjunto administrativo | Próxima qualidade por escopo; contratos e testes próprios | Não por troca de lookup | Remover avisos preservando lookup dinâmico, referências e API |
| Dependências fixadas | Runtime difere do requirements em Alembic e transitivas, conforme relatório anterior | Verificação proposta; ambiente isolado nas versões fixadas | Não | Instalação e suites nas versões fixadas, Windows/PostgreSQL separados |
| Câmbio | Cotacao/PedidoCompra não têm moeda/taxa; proposta financeira é desenho | Alta; decidir moeda-base, precisão, taxa/data/fonte, fronteira financeiro | Provável após desenho | Custo estrangeiro só incorpora após conversão explícita com histórico |
| YeastBank físico | Banco laboratorial sem integração física entregue | Unidade física, genealogia, consumo, descarte e estorno | Provável | Eventos laboratoriais separados de movimentos idempotentes |

Não houve nova certificação de hardware/Brewfather remoto ou alterações em
estoque, ledger, saldo, snapshots ou custos. Recebimento parcial segue adiado.

## Resultados finais no ambiente de geração

- Administração, hierarquia, regras e contratos novos: **111 passed in 129.01s**.
- Paridade de listas/exportação e RBAC/API: **36 passed in 43.07s**.
- Total: **147 casos distintos aprovados**, incluindo **21 novos**; sem dupla
  contagem entre as duas seleções. LegacyAPIWarning tratado como erro em ambas.
- `git diff --check`: aprovado. Patch gerado por git format-patch sobre cad38cd;
  aplicação por git am em checkout isolado, igualdade das árvores e aplicação
  reversa devem ser verificadas antes da disponibilização.
- Manual atualizado com rotas e proteções já existentes de usuário/Papel;
  layout e comportamento de seletores permanecem os atuais.
