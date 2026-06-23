"""
model/core/role.py

tesseract_role — agrupa Permissions e é atribuído a Users (m:n nos
dois sentidos). Pode nascer automaticamente via @permission(...,
role_required="x") quando o Role referenciado ainda não existir
(ver core/permissions_sync.py).
"""
from datetime import datetime, timezone

from core.db import db


class Role(db.Model):
    __tablename__ = "tesseract_role"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    users = db.relationship(
        "User", secondary="tesseract_user_roles", back_populates="roles"
    )
    permissions = db.relationship(
        "Permission", secondary="tesseract_role_permissions", back_populates="roles"
    )

    def __repr__(self) -> str:
        return f"<Role {self.name}>"
