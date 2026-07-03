"""
addons/addon_estoque/root/model/material.py

Identidade generica de qualquer item estocavel (materia-prima,
embalagem, kit/composto). Nao conhece nenhum dominio de negocio
especifico - ver docs/skills/02-nomenclatura-tabelas-e-prefixos.md e
addons/addon_estoque/docs/technical/04-modelo-de-dados.md.

`nome` e unique=True porque e a chave de negocio usada por outros
Addons ao resolver referencia fraca (skill 02: nunca FK cross-Addon) -
mesmo padrao ja usado em DeviceFunction.name/get_function_by_name.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length, choices


@label("Material")
@plural("materials")
@choices("categoria", label="Categoria")
@required("nome", message="Nome do material é obrigatório")
@max_length("nome", 200)
class Material(db.Model):
    __tablename__ = "material"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(200), unique=True, nullable=False)
    categoria = db.Column(db.String(30), nullable=False, default="materia_prima")  # materia_prima, embalagem, kit, outro
    unidade_medida = db.Column(db.String(20), nullable=True)

    peso = db.Column(db.Float, nullable=True)
    volume_calculado = db.Column(db.Float, nullable=True)
    unidade_medida_volume_calculado = db.Column(db.String(20), nullable=True)
    volume_real = db.Column(db.Float, nullable=True)
    unidade_medida_volume_real = db.Column(db.String(20), nullable=True)
    formato_fisico = db.Column(db.String(50), nullable=True)

    ativo = db.Column(db.Boolean, default=True, nullable=False)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nome": self.nome,
            "categoria": self.categoria,
            "unidade_medida": self.unidade_medida,
            "peso": self.peso,
            "volume_calculado": self.volume_calculado,
            "unidade_medida_volume_calculado": self.unidade_medida_volume_calculado,
            "volume_real": self.volume_real,
            "unidade_medida_volume_real": self.unidade_medida_volume_real,
            "formato_fisico": self.formato_fisico,
            "ativo": self.ativo,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Material {self.nome} ({self.categoria})>"
