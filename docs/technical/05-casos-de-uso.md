# 05 — Casos de Uso (Sistema)

## UC01 — Administrador cria o primeiro usuário admin

- **Ator**: Administrador (linha de comando, ainda sem usuário no sistema)
- **Pré-condição**: Banco vazio (`tesseract_user` sem linhas)
- **Fluxo principal**:
  1. `python run.py init-admin --username admin --password ...`
  2. Sistema cria `User(is_admin=True)` direto no banco
- **Fluxo alternativo**: usuário já existe → comando avisa e não duplica
- **Permissão RBAC exigida**: nenhuma (comando roda fora da API, é o
  único ponto que não passa por `has_permission()`)

## UC02 — Desenvolvedor gera CRUD a partir de um model anotado

- **Ator**: Desenvolvedor
- **Pré-condição**: model `.py` escrito com anotações (`@label`,
  `@plural`, etc.), `addon.json` válido em disco
- **Fluxo principal**:
  1. `python run.py generate --model ... --addon ... [--feature ...]`
  2. Sistema resolve prefixo de tabela, gera Service/Controller/Routes/
     3 templates HTML + 3 hooks, sincroniza permissões
- **Fluxo alternativo**: arquivo já existe sem `--overwrite` → preservado
  (hooks são *sempre* preservados, mesmo com `--overwrite`)
- **Permissão RBAC exigida**: nenhuma (comando CLI, não API)

## UC03 — Usuário com permissão cria uma cepa de levedura

- **Ator**: Usuário autenticado com `yeast_strains.create` (via Role ou `is_admin`)
- **Pré-condição**: sessão de login válida
- **Fluxo principal**:
  1. `POST /api/brewstation/yeast-strains/` com `{"name": "US-05", ...}`
  2. `permission_required` confirma a permissão
  3. `YeastStrainService.create()` persiste e retorna `201`
- **Fluxo alternativo — sem permissão**: retorna `403`
- **Fluxo alternativo — não autenticado**: retorna `401`
- **Permissão RBAC exigida**: `yeast_strains.create`

## UC04 — Usuário move uma cepa para a lixeira e restaura

- **Ator**: Usuário com `yeast_strains.trash`/`yeast_strains.restore`
- **Pré-condição**: cepa existente, não deletada
- **Fluxo principal**:
  1. `POST /.../{id}/trash` → `is_deleted=True`, some da listagem padrão
  2. `POST /.../{id}/restore` → `is_deleted=False`, volta a aparecer
- **Fluxo alternativo**: tentar `trash` numa cepa já na lixeira → `400`
- **Permissão RBAC exigida**: `yeast_strains.trash` / `yeast_strains.restore`
