"""
model/core/playground_folder.py

tesseract_playground_folder — árvore de pastas do API/SQL Playground
(skill 06, adenda "Playground v2", §8.2). Core, não passa pelo
CrudGen — mesma categoria de PlaygroundRequest (skill 00, Adendo Fase
7a). N níveis via auto-referência (`parent_id`), estilo
Collections/Folders do Postman.
"""
from datetime import datetime, timezone

from core.db import db


class PlaygroundFolder(db.Model):
    __tablename__ = "tesseract_playground_folder"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)

    # Auto-referência — N níveis. FK interna à própria tabela, permitida
    # sem restrição pela skill 02 (a restrição de FK cross-módulo é só
    # entre Addons diferentes; Core-interno é livre).
    parent_id = db.Column(db.Integer, db.ForeignKey("tesseract_playground_folder.id"), nullable=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    parent = db.relationship("PlaygroundFolder", remote_side=[id], backref="children")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
        }

    def __repr__(self) -> str:
        return f"<PlaygroundFolder {self.name!r} id={self.id}>"
