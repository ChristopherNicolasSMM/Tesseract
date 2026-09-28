"""Vínculo aprovado entre Material do estoque e item do inventário Brewfather.

material_id é referência fraca entre Addons; a associação com nomes de
ingredientes de receitas continua em IngredientMapping.
"""
from datetime import datetime, timezone

from core.db import db


class BrewfatherInventoryLink(db.Model):
    __tablename__ = "inventory_link"
    __table_args__ = (
        db.UniqueConstraint("categoria", "remote_id", name="uq_bf_inventory_remote"),
        db.UniqueConstraint("categoria", "material_id", name="uq_bf_inventory_material"),
        db.Index("ix_bf_inventory_link_material_id", "material_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(20), nullable=False)
    remote_id = db.Column(db.String(100), nullable=False)
    material_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
