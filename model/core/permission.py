"""
model/core/permission.py

tesseract_permission — "código lidera, banco segue" (skill 00/03): a
única fonte de verdade de quais permissões existem é o código (rota
gerada pelo CrudGen, Fase 4, ou @permission no model, Camada 2,
já disponível nesta fase). A UI de Admin Roles nunca cria Permission
do zero, só lê o que já foi sincronizado e associa a Role.
"""
from datetime import datetime, timezone

from core.db import db


class Permission(db.Model):
    __tablename__ = "tesseract_permission"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)  # "<plural>.<acao>"
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    roles = db.relationship(
        "Role", secondary="tesseract_role_permissions", back_populates="permissions"
    )

    def __repr__(self) -> str:
        return f"<Permission {self.name}>"
