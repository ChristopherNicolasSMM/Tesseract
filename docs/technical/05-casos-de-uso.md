# 05 — Casos de Uso (Sistema)

## UC01 — Administrador cria o primeiro usuário admin

- **Ator**: Administrador (linha de comando, banco vazio)
- **Fluxo principal**: `python run.py init-admin --username admin --password ...`
- **Fluxo alternativo**: usuário já existe → comando avisa e não duplica
- **Permissão**: nenhuma (fora da API)

## UC02 — Usuário recupera acesso perdido

- **Ator**: Administrador (via CLI) ou o próprio admin (via tela, pra
  outro usuário)
- **Fluxo principal (CLI)**: `python run.py reset-password --username X --password Y [--reactivate]`
- **Fluxo principal (tela)**: `/admin/users/<id>` → "Redefinir senha"
- **Fluxo alternativo**: autodesativação — bloqueada explicitamente na
  tela (`/admin/users/<id>/deactivate` do próprio usuário logado),
  mas possível via API (efeito: sessão desautentica, ver `BACKLOG.md`)
- **Permissão**: `admin`

## UC03 — Desenvolvedor gera CRUD a partir de um model anotado

- **Ator**: Desenvolvedor
- **Fluxo principal**: `python run.py generate --model ... --addon ... [--feature ...]`
- **Fluxo alternativo**: arquivo já existe sem `--overwrite` → preservado
  (hooks sempre preservados, mesmo com `--overwrite`)
- **Permissão**: nenhuma (CLI)

## UC04 — Desenvolvedor altera coluna de um model já existente

- **Ator**: Desenvolvedor
- **Pré-condição**: tabela já existe no banco (`db.create_all()` não
  resolve este caso)
- **Fluxo principal**: editar o model → `python run.py db migrate -m "..."` → `python run.py db upgrade`
- **Permissão**: nenhuma (CLI)

## UC05 — Usuário com permissão cria/edita/exclui um registro (CRUD genérico)

- **Ator**: Usuário autenticado com a Permission correspondente
- **Fluxo principal**: tela de listagem → "+" expande formulário →
  criar → editar no detalhe → lixeira → restaurar → excluir
  permanente (só se já estiver na lixeira)
- **Fluxo alternativo — sem permissão**: 403
- **Fluxo alternativo — não autenticado**: redireciona pra `/login`
- **Permissão**: `<plural>.<ação>`

## UC06 — Administrador cria um Role e associa Permissions

- **Ator**: Administrador
- **Fluxo principal**: `/admin/roles/` → criar Role → `/admin/roles/<id>`
  → marcar Permissions agrupadas por módulo → salvar
- **Fluxo alternativo**: excluir Role com usuário atribuído → bloqueado
- **Permissão**: `admin`

## UC07 — Administrador investiga/restaura uma versão de arquivo gerado

- **Ator**: Administrador
- **Fluxo principal**: `/admin/versioning/` → busca arquivo → histórico
  → seleciona duas versões → diff → restaurar (grava no disco + novo
  snapshot `origin=RESTORE`)
- **Permissão**: `admin`

## UC08 — Usuário troca o próprio tema (claro/escuro)

- **Ator**: qualquer usuário autenticado
- **Fluxo principal**: menu do usuário ou `/perfil/` → alternar tema →
  `POST /api/auth/update-theme` → persiste por usuário
- **Permissão**: nenhuma (próprio usuário)
