"""
model/core/designer_page.py

tesseract_designer_page — página construída visualmente no Designer
(Fase 7c). Adaptado de models/page.py (DEVStationFlask), sem
`project_id`: o DEVStationFlask original organizava páginas dentro de
"Projetos" (conceito do Designer dele, um app builder completo); o
Tesseract não tem isso — uma página do Designer é uma tela navegável
de Core, como qualquer outra (entra no catálogo de Transações se o
usuário quiser).
"""
from datetime import datetime, timezone

from core.db import db


class DesignerPage(db.Model):
    __tablename__ = "tesseract_designer_page"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False, default="Página")
    title = db.Column(db.String(200), nullable=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)

    canvas_width = db.Column(db.Integer, default=1280, nullable=False)
    canvas_height = db.Column(db.Integer, default=720, nullable=False)
    canvas_bg = db.Column(db.String(20), default="#f6f9ff", nullable=False)

    is_published = db.Column(db.Boolean, default=False, nullable=False)
    permission_required = db.Column(db.String(150), nullable=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    components = db.relationship(
        "DesignerComponent", backref="page",
        cascade="all, delete-orphan",
        order_by="DesignerComponent.z_index",
    )

    def to_dict(self, include_components: bool = False) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "title": self.title or self.name,
            "slug": self.slug,
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "canvas_bg": self.canvas_bg,
            "is_published": self.is_published,
            "permission_required": self.permission_required,
        }
        if include_components:
            d["components"] = [c.to_dict() for c in self.components]
        return d

    def __repr__(self) -> str:
        return f"<DesignerPage id={self.id} name={self.name!r} slug={self.slug!r}>"
