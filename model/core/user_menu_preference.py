"""
model/core/user_menu_preference.py

tesseract_user_menu_preference — override individual (por usuário) de
ordem/colapso de menu (skill 07 + árvore skill 10). Colunas nullable =
"herda o padrão global" (system_config, chaves core.menu.*).
"""
from datetime import datetime, timezone

from core.db import db


class UserMenuPreference(db.Model):
    __tablename__ = "tesseract_user_menu_preference"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=False, unique=True)

    # Skill 10: dict {parent_code|"__root__": [code_filho_em_ordem]} — ordenação
    # por pai, não uma lista global de um nível só. null = herda o padrão global.
    order_overrides_json = db.Column(db.JSON, nullable=True)
    # Skill 10: lista de códigos (qualquer nível da árvore). null = herda o padrão global.
    collapsed_nodes_json = db.Column(db.JSON, nullable=True)
    sidebar_collapsed = db.Column(db.Boolean, nullable=True)  # null = herda o padrão global

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<UserMenuPreference user_id={self.user_id}>"
