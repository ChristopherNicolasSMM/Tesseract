"""
addons/addon_estoque/root/model/fornecedor_endereco.py

Fase 3 (skill 23) — vínculo Fornecedor -> Endereco (1:N). FK real dos
dois lados (mesmo Addon, permitido pela skill 02). `principal`: no
máximo um `true` por fornecedor no total (não por tipo_endereco) -
imposto por índice único parcial, mesmo padrão de
MaterialUnidade.is_unidade_base.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, enum_field, field_labels


@label("Endereço do Fornecedor")
@plural("fornecedor_enderecos")
@required("fornecedor_id", message="Fornecedor é obrigatório")
@required("endereco_id", message="Endereço é obrigatório")
@required("tipo_endereco", message="Tipo de endereço é obrigatório")
@enum_field("tipo_endereco", options=[
    ("cobranca", "Cobrança"), ("entrega", "Entrega"),
    ("correspondencia", "Correspondência"), ("faturamento", "Faturamento"),
    ("outro", "Outro"),
])
@field_labels({
    "fornecedor_id": "Fornecedor",
    "endereco_id": "Endereço",
    "tipo_endereco": "Tipo de Endereço",
    "principal": "Principal",
})
class FornecedorEndereco(db.Model):
    __tablename__ = "fornecedor_endereco"

    __table_args__ = (
        db.Index(
            "uq_fornecedor_endereco_principal", "fornecedor_id",
            unique=True, sqlite_where=db.text("principal = 1 AND is_deleted = 0"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    fornecedor_id = db.Column(db.Integer, db.ForeignKey("fornecedor.id", ondelete="CASCADE"), nullable=False, index=True)
    fornecedor = db.relationship("Fornecedor", backref=db.backref("enderecos", lazy=True))

    endereco_id = db.Column(db.Integer, db.ForeignKey("endereco.id", ondelete="RESTRICT"), nullable=False, index=True)
    endereco = db.relationship("Endereco")

    tipo_endereco = db.Column(db.String(20), nullable=False)
    principal = db.Column(db.Boolean, default=False, nullable=False)
    observacoes = db.Column(db.Text, nullable=True)

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
            "fornecedor_id": self.fornecedor_id,
            "endereco_id": self.endereco_id,
            "tipo_endereco": self.tipo_endereco,
            "principal": self.principal,
            "observacoes": self.observacoes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<FornecedorEndereco fornecedor_id={self.fornecedor_id} tipo={self.tipo_endereco}>"
