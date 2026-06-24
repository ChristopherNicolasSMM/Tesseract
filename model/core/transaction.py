"""
model/core/transaction.py

tesseract_transaction — catálogo de pontos de entrada navegáveis
(skill 00, termo "Transação"). Adaptado de transactions/catalog.py +
models/transaction.py (DEVStationFlask).

Duas diferenças deliberadas em relação ao original:
1. Sem `min_profile` (tier simplificado USER/DEVELOPER/ADMIN) — usa
   `permission_required`, resolvido pelo RBAC real do Tesseract
   (`User.has_permission()`). Nenhum sistema de autorização paralelo.
2. Sem o conceito de "Plugin" do DEVStationFlask (descoberta de
   pasta, ativação separada) — é redundante com o `ModuleManager` que
   o Tesseract já tem. Quem contribui uma Transaction é um
   Addon/Feature/Plugin já registrado pelo `ModuleManager`;
   `source_module` só registra a origem, não controla ativação.
"""
from datetime import datetime, timezone

from core.db import db


class Transaction(db.Model):
    __tablename__ = "tesseract_transaction"

    id = db.Column(db.Integer, primary_key=True)

    code = db.Column(db.String(50), unique=True, nullable=False, index=True)  # TX_YEAST_BANK
    label = db.Column(db.String(100), nullable=False)
    group = db.Column(db.String(50), nullable=False, default="Core")
    description = db.Column(db.String(300), nullable=True)
    icon = db.Column(db.String(50), default="bi-app")  # classe Bootstrap Icons

    route = db.Column(db.String(300), nullable=False)
    route_params = db.Column(db.JSON, default=lambda: {})

    # RBAC real — não um tier separado (ver docstring do módulo).
    permission_required = db.Column(db.String(150), nullable=True, index=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_standard = db.Column(db.Boolean, default=True, nullable=False)  # False = contribuída por Addon/Plugin

    source_module = db.Column(db.String(100), nullable=True)  # nome do Addon/Plugin de origem

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "label": self.label,
            "group": self.group,
            "description": self.description,
            "icon": self.icon,
            "route": self.route,
            "route_params": self.route_params or {},
            "permission_required": self.permission_required,
            "is_active": self.is_active,
            "is_standard": self.is_standard,
            "source_module": self.source_module,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Transaction code={self.code} label={self.label!r}>"
