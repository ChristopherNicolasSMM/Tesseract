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

    # Fase 10 (Patch 1, schema; Patch 6, resolver real — skill 16).
    # Referência fraca (nunca FK — skill 02). Achado real corrigido no
    # Patch 6: o valor esperado é o PLURAL — mesmo formato de
    # FieldRule.entity_key, UserListPreference.list_key e do prefixo
    # de Permission de toda entidade do CrudGen (ex.: "yeast_strains",
    # não "yeast_strain") — é contra essa convenção que
    # core/designer_menu_override.py resolve a Transaction a trocar
    # (via permission_required == "<replaces_entity_key>.list").
    replaces_entity_key = db.Column(db.String(150), nullable=True)
    replaces_view = db.Column(db.String(20), nullable=True)  # "manage" | "detail"
    # Checkbox: só tem efeito com replaces_entity_key preenchido e
    # replaces_view == "manage" (só a tela de listagem vira item de
    # menu por conta própria — "detail" nunca tem Transaction própria
    # pra trocar). True = a rota original do CrudGen some do MENU
    # (nunca da aplicação — continua acessível direto, por decisão
    # registrada em BACKLOG.md/skill 16, para permitir debug/
    # conferência de valores).
    replace_in_menu = db.Column(db.Boolean, default=False, nullable=False)

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
            "replaces_entity_key": self.replaces_entity_key,
            "replaces_view": self.replaces_view,
            "replace_in_menu": self.replace_in_menu,
        }
        if include_components:
            d["components"] = [c.to_dict() for c in self.components]
        return d

    def __repr__(self) -> str:
        return f"<DesignerPage id={self.id} name={self.name!r} slug={self.slug!r}>"
