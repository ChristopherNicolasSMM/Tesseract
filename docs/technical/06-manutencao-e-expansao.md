# 06 — Manutenção e Expansão (Sistema)

## Como adicionar um campo a um model existente

1. Editar a coluna em `model/<entidade>.py` (Addon/Feature).
2. Rodar `python run.py generate --model ... --addon ... [--feature ...] --overwrite`.
3. O CrudGen regenera `service.py`/`controller.py`/`routes.py`/templates
   HTML — **mas nunca os `*_hooks.py`** (preservados sempre).
4. Se a coluna precisa de uma migration real em produção (Postgres já
   com dados), criar a migration manualmente — o Tesseract ainda não
   tem Alembic integrado (ver "Pontos de extensão conhecidos" abaixo).

## Como adicionar uma nova Feature a um Addon existente

1. Criar `addons/addon_x/features/feature_y/feature.json` com
   `table_prefix_suffix` único dentro do Addon.
2. Criar `addons/addon_x/features/feature_y/feature.py` com
   `__module__ = "FeatureY"` e a classe herdando `FeatureBase`.
3. Implementar `register_models()` (obrigatório) e `register_routes()`
   (opcional).
4. Adicionar a Feature em `AddonX.get_features()`.
5. Escrever o model anotado, rodar `generate`.
6. Preencher `docs/technical/01-*.md` e `docs/manual/01-*.md` da Feature
   (checklist da skill 03/04).

## Como depreciar/remover uma Feature ou Addon sem deixar tabela órfã

Ainda não há uma rotina automatizada para isso (registrado como lacuna
— nenhum item de backlog ainda aberto para isso explicitamente, mas
fica documentado aqui como ponto de atenção futuro). Hoje, remover
significa:

1. Migration manual de `DROP TABLE` para cada tabela da Feature/Addon.
2. Remover a pasta do Addon/Feature do disco.
3. Remover a entrada de `tesseract_module_state` (se existir).
4. As Permissions associadas (`<plural>.<acao>`) ficam órfãs no banco —
   não há limpeza automática ainda.

## Pontos de extensão conhecidos

- **`EventBus`** (`core/event_bus.py`) — qualquer Addon pode publicar
  ou escutar eventos (`event_bus.publish`/`subscribe`) sem acoplamento
  direto a outro Addon. Hoje só existe 1 evento real:
  `core.module.activated`.
- **Hooks** (`*_hooks.py`) — todo arquivo gerado pelo CrudGen tem um
  par de hooks nunca sobrescrito, para customização sem editar código
  gerado.
- **`core/versioning.py`** — `snapshot_if_needed()` está pronto para
  ser chamado por qualquer escrita de arquivo que se queira versionar,
  não só pelo CrudGen.
- **Migrations reais (Alembic)** — ainda não integrado. Hoje
  `db.create_all()` só cria tabela que não existe; não há suporte a
  alterar coluna existente em produção. Avaliar quando o primeiro
  Addon for usado com dados reais em Postgres.
