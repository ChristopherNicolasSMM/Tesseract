"""
model/core/transaction.py

tesseract_transaction — catálogo de pontos de entrada navegáveis
(skill 00, termo "Transação"). Adaptado de transactions/catalog.py +
models/transaction.py (DEVStationFlask).

Três diferenças deliberadas em relação ao original:
1. Sem `min_profile` (tier simplificado USER/DEVELOPER/ADMIN) — usa
   `permission_required`, resolvido pelo RBAC real do Tesseract
   (`User.has_permission()`). Nenhum sistema de autorização paralelo.
2. Sem o conceito de "Plugin" do DEVStationFlask (descoberta de
   pasta, ativação separada) — é redundante com o `ModuleManager` que
   o Tesseract já tem. Quem contribui uma Transaction é um
   Addon/Feature/Plugin já registrado pelo `ModuleManager`;
   `source_module` só registra a origem, não controla ativação.
3. Árvore de profundidade arbitrária via `parent_id`/`order_index`
   (skill 10) — um "grupo" é uma Transação sem `route` (nó-pasta puro,
   só agrupa filhos). Substitui o campo `group` (string plana, um
   único nível) que existia até a skill 10.
"""
from datetime import datetime, timezone

from core.db import db


class Transaction(db.Model):
    __tablename__ = "tesseract_transaction"

    id = db.Column(db.Integer, primary_key=True)

    code = db.Column(db.String(50), unique=True, nullable=False, index=True)  # TX_YEAST_BANK
    label = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300), nullable=True)
    icon = db.Column(db.String(50), default="bi-app")  # classe Bootstrap Icons

    # Nullable (skill 10) — nó-pasta puro (só agrupa filhos) não navega.
    route = db.Column(db.String(300), nullable=True)
    route_params = db.Column(db.JSON, default=lambda: {})

    # Árvore (skill 10). NULL = raiz. order_index ordena irmãos sob o
    # mesmo pai — não é global, é por nível.
    parent_id = db.Column(db.Integer, db.ForeignKey("tesseract_transaction.id"), nullable=True)
    order_index = db.Column(db.Integer, nullable=False, default=0)

    # RBAC real — não um tier separado (ver docstring do módulo).
    permission_required = db.Column(db.String(150), nullable=True, index=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_standard = db.Column(db.Boolean, default=True, nullable=False)  # False = contribuída por Addon/Plugin

    source_module = db.Column(db.String(100), nullable=True)  # nome do Addon/Plugin de origem

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    children = db.relationship(
        "Transaction",
        backref=db.backref("parent", remote_side=[id]),
        order_by="Transaction.order_index",
    )

    @property
    def is_folder(self) -> bool:
        """Nó-pasta puro (skill 10) — agrupa filhos, nunca navega."""
        return self.route is None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "label": self.label,
            "description": self.description,
            "icon": self.icon,
            "route": self.route,
            "route_params": self.route_params or {},
            "parent_id": self.parent_id,
            "order_index": self.order_index,
            "permission_required": self.permission_required,
            "is_active": self.is_active,
            "is_standard": self.is_standard,
            "source_module": self.source_module,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Transaction code={self.code} label={self.label!r}>"
