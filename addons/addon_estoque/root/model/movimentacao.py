"""
addons/addon_estoque/root/model/movimentacao.py

Ledger de movimentacao de estoque - imutavel apos criado. Correcao de
lancamento errado e sempre um NOVO registro (tipo_movimentacao="ajuste"),
nunca UPDATE/DELETE de um lancamento existente. Por isso nao tem
soft-delete (skill 02) como as demais tabelas do Addon - e ledger
contabil, nao entidade de cadastro.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, choices, min_value


@label("Movimentação de Estoque")
@plural("movimentacaos")
@choices("tipo_movimentacao", label="Tipo")
@required("material_id", message="Material é obrigatório")
@required("tipo_movimentacao", message="Tipo da movimentação é obrigatório")
@min_value("quantidade", 0, message="Quantidade não pode ser negativa")
class Movimentacao(db.Model):
    __tablename__ = "movimentacao"

    id = db.Column(db.Integer, primary_key=True)

    material_id = db.Column(db.Integer, db.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False, index=True)
    material = db.relationship("Material", backref=db.backref("movimentacoes", lazy=True))

    tipo_movimentacao = db.Column(db.String(10), nullable=False)  # entrada, saida, ajuste
    quantidade = db.Column(db.Float, nullable=False)
    custo_unitario = db.Column(db.Float, nullable=True)
    custo_total = db.Column(db.Float, nullable=True)
    lote_fornecedor = db.Column(db.String(100), nullable=True)
    data_validade = db.Column(db.Date, nullable=True)
    data_movimentacao = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    usuario_id = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)

    observacoes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "material_id": self.material_id,
            "tipo_movimentacao": self.tipo_movimentacao,
            "quantidade": self.quantidade,
            "custo_unitario": self.custo_unitario,
            "custo_total": self.custo_total,
            "lote_fornecedor": self.lote_fornecedor,
            "data_validade": self.data_validade.isoformat() if self.data_validade else None,
            "data_movimentacao": self.data_movimentacao.isoformat() if self.data_movimentacao else None,
            "usuario_id": self.usuario_id,
            "observacoes": self.observacoes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Movimentacao {self.tipo_movimentacao} material_id={self.material_id} qtd={self.quantidade}>"
