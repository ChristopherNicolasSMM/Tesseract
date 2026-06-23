"""
annotations/

Decorators de metadado usados pelo CrudGen (Fase 4) para anotar models
e gerar Controller/Service/Templates a partir deles.

Portado da arquitetura de anotações do PyTeca (preservada como está,
ver decisão registrada na conversa de arquitetura) — populado na Fase 4.
"""

# ---- @permission: Camada 2 (granularidade de negócio) ----
# Camada 1 (permissão automática de rota gerada pelo CrudGen) entra na
# Fase 4 — ainda não existe CrudGen nesta fase. @permission cobre ações
# de negócio que não mapeiam 1:1 para uma rota, ou quando se quer
# atribuir a permissão a um Role já no momento da sincronização.
def permission(action: str, role_required: str | None = None, description: str | None = None):
    """
    Uso no model:
        @permission("trash", role_required="brewmaster",
                     description="Mover lote para a lixeira")
        class Recipe(db.Model):
            ...

    Nome de permissão sincronizado: "<plural>.<action>" — mesmo padrão
    que a Camada 1 vai usar na Fase 4, para nunca haver dois formatos
    de nome coexistindo (skill 00).
    """
    def decorator(cls):
        if not hasattr(cls, '_permissions'):
            cls._permissions = []
        cls._permissions.append({
            "action": action,
            "role_required": role_required,
            "description": description or f"Permite '{action}' em {cls.__name__}",
        })
        return cls
    return decorator


def get_permissions_meta(cls) -> list[dict]:
    """Retorna as permissões de negócio (@permission) declaradas no model."""
    return getattr(cls, '_permissions', [])
