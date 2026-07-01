"""
core/permissions_sync.py

Sincronização código -> banco de Permission. "Código lidera, banco
segue" (skill 00/03): a UI de Admin Roles nunca cria Permission do
zero, só lê o que já foi sincronizado.

Camada 1 (automática): toda entidade gerada pelo CrudGen ganha 7
permissões padrão (list/detail/create/update/trash/restore/
delete_permanent), sem precisar de nenhuma anotação explícita.
Camada 2 (@permission no model): ações de negócio que não mapeiam
1:1 para uma rota padrão.
"""
import logging

from core.db import db
from annotations import get_permissions_meta

logger = logging.getLogger(__name__)

# Mantido em um único lugar para nunca dessincronizar do que o CrudGen
# realmente gera (core/crudgen/generator.py).
STANDARD_CRUD_ACTIONS = [
    ("list", "Listar"),
    ("detail", "Visualizar detalhe"),
    ("create", "Criar"),
    ("update", "Editar"),
    ("trash", "Mover para lixeira"),
    ("restore", "Restaurar da lixeira"),
    ("delete_permanent", "Excluir permanentemente"),
]


def sync_model_permissions(model_class, plural: str) -> dict:
    """
    Idempotente — pode ser chamado repetidamente (a cada `generate`)
    sem duplicar Permission nem apagar associação Role<->Permission
    feita manualmente via UI.
    """
    from model.core.permission import Permission
    from model.core.role import Role

    created, existing = [], []

    # ── Camada 1: permissões automáticas das 7 ações de CRUD ────────────
    for action, description in STANDARD_CRUD_ACTIONS:
        perm_name = f"{plural}.{action}"
        perm = Permission.query.filter_by(name=perm_name).first()
        if perm is None:
            perm = Permission(name=perm_name, description=f"{description} — {plural}")
            db.session.add(perm)
            created.append(perm_name)
        else:
            existing.append(perm_name)

    # ── Camada 2: permissões de negócio via @permission no model ───────
    for meta in get_permissions_meta(model_class):
        perm_name = f"{plural}.{meta['action']}"
        perm = Permission.query.filter_by(name=perm_name).first()
        if perm is None:
            perm = Permission(name=perm_name, description=meta["description"])
            db.session.add(perm)
            created.append(perm_name)
        else:
            existing.append(perm_name)
            if meta["description"] and perm.description != meta["description"]:
                perm.description = meta["description"]

        db.session.flush()

        role_required = meta.get("role_required")
        if role_required:
            role = Role.query.filter_by(name=role_required).first()
            if role is None:
                role = Role(
                    name=role_required,
                    description="Criado automaticamente via @permission",
                )
                db.session.add(role)
                db.session.flush()
            if perm not in role.permissions:
                role.permissions.append(perm)

    db.session.commit()

    if created:
        logger.info("Permissões sincronizadas (novas): %s", ", ".join(created))

    return {"created": created, "existing": existing}


# ── Permissões fixas de telas de Core (não-CrudGen) ─────────────────────────
# Mesmo padrão "código lidera, banco segue" do catálogo de Transações
# (core/transactions_catalog.py + core/transactions_sync.py) — aqui para
# telas de Core escritas à mão (skill 00, Adendo Fase 7a) que precisam de
# permissão própria em vez de reaproveitar o "admin" genérico.
CORE_FIXED_PERMISSIONS = [
    ("model_definitions.create", "Criar/editar rascunho no Model Builder"),
    ("model_definitions.generate", "Disparar geração de código a partir de um rascunho do Model Builder"),
    ("model_definitions.view", "Ver rascunhos do Model Builder"),
    ("system_config.menu_settings", "Editar o padrão global de ordem/colapso de menu (skill 07)"),
]


def sync_core_fixed_permissions() -> dict:
    from model.core.permission import Permission

    created, existing = [], []
    for perm_name, description in CORE_FIXED_PERMISSIONS:
        perm = Permission.query.filter_by(name=perm_name).first()
        if perm is None:
            db.session.add(Permission(name=perm_name, description=description))
            created.append(perm_name)
        else:
            existing.append(perm_name)
    db.session.commit()

    if created:
        logger.info("Permissões fixas de Core sincronizadas (novas): %s", ", ".join(created))

    return {"created": created, "existing": existing}
