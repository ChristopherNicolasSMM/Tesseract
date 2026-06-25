"""
model/core/designer_component.py

tesseract_designer_component — um componente posicionado dentro de
uma DesignerPage. Portado quase 1:1 de models/component.py
(DEVStationFlask) — schema idêntico (x/y/width/height/z_index +
properties/events/rules em JSON), só o nome da tabela/FK mudou.

`rules` aqui é onde o catálogo da Fase 7b (core/rules_catalog.py)
finalmente ganha um alvo de verdade: Visibilidade/Cálculo referenciam
`source_id`/`target_id` que agora são o `id` real de outro
DesignerComponent na mesma página — antes da existência desta tabela,
esses grupos do catálogo não tinham nenhum componente real pra apontar.
"""
from datetime import datetime, timezone

from core.db import db

# Tipos de componente suportados nesta fase — escopo deliberadamente
# menor que o catálogo completo do DEVStationFlask (sem datagrid/
# pagination/groupbox ainda, que dependem de binding OData mais
# elaborado — ver BACKLOG.md).
COMPONENT_TYPES = ("heading", "label", "textbox", "button", "image", "divider")


class DesignerComponent(db.Model):
    __tablename__ = "tesseract_designer_component"

    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer, db.ForeignKey("tesseract_designer_page.id"), nullable=False, index=True)

    type = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)

    x = db.Column(db.Integer, default=100, nullable=False)
    y = db.Column(db.Integer, default=100, nullable=False)
    width = db.Column(db.Integer, default=150, nullable=False)
    height = db.Column(db.Integer, default=40, nullable=False)
    z_index = db.Column(db.Integer, default=1, nullable=False)

    properties = db.Column(db.JSON, default=lambda: {})
    events = db.Column(db.JSON, default=lambda: {})
    rules = db.Column(db.JSON, default=lambda: [])

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "page_id": self.page_id,
            "type": self.type,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "z_index": self.z_index,
            "properties": self.properties or {},
            "events": self.events or {},
            "rules": self.rules or [],
        }

    def __repr__(self) -> str:
        return f"<DesignerComponent id={self.id} type={self.type!r} name={self.name!r}>"
