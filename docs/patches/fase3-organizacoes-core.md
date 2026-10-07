# Fase 3 — identidade compartilhada de organizações

Implementado no ambiente de geração; aplicação e validação local pendentes.
Base cdbd114. Usuário confirmou aplicação do pacote de ferramentas/integrações;
confirmação dos testes locais permanece separada da aplicação.

## Decisões funcionais confirmadas

- Moeda-base por organização.
- Addon financeiro primeiro, fornecendo serviço público de conversão validada.
- Cadastro de organização no Core, compartilhável entre módulos; segregação do
  estoque é um pacote posterior.

Não havia entidade Organization no checkout: User.empresa é texto de perfil,
não identidade empresarial. Saldo é global por Material; pedidos não carregam
organização/moeda/taxa. A implantação financeira depende dessa identidade antes
de representar política monetária por organização. Não é seguro transformar
User.empresa em cadastro nem atribuir registros antigos a uma organização.

## Pacote entregue

Tabela Core tesseract_organization com ID, código de negócio permanente, nome,
estado ativo e timestamps. Código normalizado em ASCII maiúsculo, 1–40
caracteres, letras/números/hífen/sublinhado; exclusivo. Nome obrigatório até 120
caracteres. Administradores podem criar, renomear e inativar/reativar. Código
não muda após criação; não há operação de exclusão. Inativação preserva a
identidade para referências futuras e resolução histórica explícita.

Tela manual `/admin/organizations/`, API `/api/admin/organizations/` e entrada
Organizações no grupo Administração. Reutilizam login, permission_required
admin, layout e classes de tema existentes. Dados exibidos são escapados por
Jinja; booleanos/payloads são validados no serviço manual. Conflito de código
ou gravação reverte a transação; a sessão continua utilizável. Nenhum arquivo
CrudGen gerado foi editado.

Contrato em `services/core/organization_service.py`:
- `resolve_organization(id, require_active=True)` retorna cópia de identidade.
- `resolve_organization_by_code(code, require_active=True)` permite referência
  fraca por chave de negócio sem consultar tabelas Core diretamente.
- `require_active=False` é opção explícita de consulta histórica de identidade
  inativa; a autorização pertence ao chamador. Resolver não grava nem confirma
  transação. A API administrativa pode consultar inativos.

Annotations declaram plural organizations e display_field name. O endpoint
genérico de opções já existente exige login e pode listar essas identidades;
não estabelece acesso aos dados financeiros nem membership. Configuração de
moeda/custos e autorização por organização pertencem aos próximos contratos.
Não existe isolamento de tenant, organização atual da sessão ou associação
Usuário–Organização nesta entrega.

## Migration e aplicação

Nova revisão a71c8d32f906, filha de f8c214ab709e. Cria tabela vazia; não cria
organização padrão, não escolhe moeda e não altera saldos, custos ou histórico.
Reconhece tabela já criada pelos models apenas se colunas, tipos, comprimentos,
nulabilidade, PK e unicidade do código forem compatíveis. Schema divergente
interrompe sem adaptação silenciosa. Downgrade recusa remover tabela com
organizações existentes; foi ensaiado somente em banco temporário.

```powershell
git -c gc.auto=0 am --keep-cr .\tesseract-fase3-organizacoes-core.patch
python -m flask db upgrade
```

**Este pacote requer flask db upgrade.** Executar antes de iniciar normalmente
a aplicação; reiniciar depois. Não usar stamp para pular a revisão. Não executar
downgrade como conferência no banco instalado.

Testes locais:

```powershell
python -m pytest tests/test_core_organizations.py tests/test_migrations_idempotent.py tests/test_migration_schema_compat.py tests/test_phase2_rbac.py tests/test_admin_smart_list_parity.py tests/test_menu_hierarquico.py tests/test_admin_users_pages.py -q -W error::sqlalchemy.exc.LegacyAPIWarning --tb=short
```

Runtime de geração mantido: Python 3.12.3, Flask 3.1.3, Flask-SQLAlchemy 3.1.1,
SQLAlchemy 2.0.51 e pytest 9.1.1. Execução via /usr/bin/python3 com PYTHONPATH do
venv-yeast-audit registrado no ciclo. Alembic 1.20.0 difere do fixado 1.18.4;
continua pendente a reprodução integral do requirements.txt, Windows e
PostgreSQL. Não houve instalação ou upgrade de dependências.

## Conferência visual

1. Abrir `/admin/organizations/` como administrador; conferir a entrada do menu.
2. Criar código BREW_TEST com nome de teste. Verificar código permanente,
   renomear, inativar e reativar; tentar código duplicado em novo cadastro.
3. Buscar pelo nome/código; verificar caracteres especiais exibidos como texto.
   Repetir apresentação nos temas claro/escuro. Nenhum seletor financeiro novo
   foi adicionado nesta fundação.
4. A API GET/POST da coleção e GET/PUT por ID usam a mesma regra. PUT tentando
   trocar código deve retornar 409; DELETE por ID deve retornar 405.
5. Usuário comum não pode administrar: tela/API retornam 403 após login. Acesso
   anônimo à API exige autenticação. Registrar organização de teste inativa ao
   final; a identidade é permanente e não há exclusão pelo cadastro.

Conferência visual humana permanece pendente. Testes cobrem escaping, validação,
permissões, código estável, inativação, conflitos, rollback, contratos públicos,
migration idempotente, incompatibilidade e downgrade protegido.

## Sequência financeira após esta fundação

| Pacote | Estado / dependência | Migration | Conclusão |
| --- | --- | --- | --- |
| Financeiro: catálogo de moedas e política por organização | Próximo desenho; usar identidade pública Core, definir precisão e arredondamento explícitos | Sim | Configuração sem moeda padrão presumida; política em uso protegida |
| Financeiro: taxas e serviço público de conversão | Depois do catálogo; par/direção, vigência, fonte/tipo e precisão | Sim para histórico persistente | Taxa positiva finita, resultado/snapshot congelado; sem busca ou paridade automática |
| Compras/Estoque: contexto organizacional e moeda | Depois do serviço; mapear propriedade de documentos, material/saldo e legados | Sim, desenho pendente | Nunca misturar custos de moedas-base/organizações diferentes; entrada só em base validada |
| Financeiro: pagamentos e diferença cambial | Proposto, posterior ao custo do recebimento | A determinar | Diferenças pertencem ao pagamento sem recalcular ledger/custos anteriores |

YeastBank físico, recebimento parcial, hardware real e integração remota seguem
frentes separadas. A moeda da cotação ainda não foi implementada; este pacote
é sua dependência de identidade, não um fluxo de compra estrangeira completo.

## Resultados exatos no ambiente de geração

- Seleção inicial de organizações, migrations e RBAC: **54 passed in 58.05s**.
- Paridade administrativa, hierarquia, usuários e resolução por código:
  **52 passed in 65.06s**.
- Seleção final de todos os testes novos, após validar IDs de escrita:
  **33 passed in 31.38s**.
- Total sem repetição: **111 casos distintos** (33 novos e 78 existentes).
  Os 27 testes novos da seleção inicial e o caso de código da segunda foram
  contados dentro dos 33 finais, uma vez cada.
- LegacyAPIWarning tratado como erro. Testes de migrations exercitam comandos
  Flask reais em SQLite temporário, inclusive upgrade até a71c8d32f906 e
  downgrade de tabela vazia. Dados de organização bloqueiam downgrade.
- `git diff --check` aprovado. Patch gerado por git format-patch; protocolo de
  entrega exige git am isolado sobre cdbd114, igualdade das árvores e
  git apply --reverse --check. A alteração preexistente logo.png fica fora.
