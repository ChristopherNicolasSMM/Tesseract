"""
model/core/module_state.py

Tabela tesseract_module_state — estado de ativação de Addons e Plugins.
Decisão de arquitetura: estado vive no banco (padrão DEVStationFlask),
não em arquivo (padrão antigo do BrewStation) — ver conversa de
arquitetura, comparativo PluginManager vs registry.py.
"""
from datetime import datetime, timezone

from core.db import db


class ModuleState(db.Model):
    __tablename__ = "tesseract_module_state"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    module_type = db.Column(db.String(10), nullable=False)  # "addon" | "plugin"
    version = db.Column(db.String(20), nullable=False)
    is_installed = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    installed_at = db.Column(db.DateTime)
    activated_at = db.Column(db.DateTime)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ModuleState {self.name} type={self.module_type} "
            f"active={self.is_active}>"
        )
