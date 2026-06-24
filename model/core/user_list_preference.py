"""
model/core/user_list_preference.py

tesseract_user_list_preference — preferência de colunas visíveis e
ordem, por usuário e por lista (uma linha por combinação
usuário+`list_key`). `list_key` é o `plural` da entidade (ex.:
"yeast_strains") — não precisa de FK pra isso, é só uma string,
porque a lista pode ser de qualquer Addon/Feature (Core não pode ter
FK pra tabela de domínio).

Tabela nova — não exige migration (db.create_all() já resolve tabela
que nunca existiu; só ALTER de tabela existente precisa de
Flask-Migrate, ver BACKLOG.md).
"""
from datetime import datetime, timezone

from core.db import db


class UserListPreference(db.Model):
    __tablename__ = "tesseract_user_list_preference"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=False, index=True)
    list_key = db.Column(db.String(150), nullable=False, index=True)  # plural da entidade

    visible_columns_json = db.Column(db.JSON, default=lambda: [])
    column_order_json = db.Column(db.JSON, default=lambda: [])

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "list_key", name="uq_user_list_pref_user_list"),
    )

    def __repr__(self) -> str:
        return f"<UserListPreference user_id={self.user_id} list_key={self.list_key}>"
