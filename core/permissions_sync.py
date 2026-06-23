"""
core/permissions_sync.py

Sincronização código -> banco de Permission (Camada 2 — @permission
nos models). "Código lidera, banco segue" (skill 00/03): a UI de Admin
Roles nunca cria Permission do zero, só lê o que já foi sincronizado.

Camada 1 (permissão automática por rota gerada pelo CrudGen) entra na
Fase 4 — este módulo já está pronto para ganhar essa camada depois,
sem mudar a assinatura de sync_model_permissions().
"""
import logging

from core.db import db
from annotations import get_permissions_meta

logger = logging.getLogger(__name__)


def sync_model_permissions(model_class, plural: str) -> dict:
    """
    Idempotente — pode ser chamado repetidamente sem duplicar
    Permission nem apagar associação Role<->Permission feita manualmente
    via UI.
    """
    from model.core.permission import Permission
    from model.core.role import Role

    created, existing = [], []

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
