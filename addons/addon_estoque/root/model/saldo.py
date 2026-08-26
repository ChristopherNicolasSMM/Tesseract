"""
addons/addon_estoque/root/model/saldo.py

Cache materializado do saldo atual de um Material - 1:1. Atualizado a
cada Movimentacao (services/material_service.py) e, futuramente, por
um mecanismo de recalculo manual sob demanda (nao desenhado ainda -
ver addons/addon_estoque/docs/technical/01-visao-geral.md, pendencias).

`status` e propriedade Python simples (nao hybrid_property - padrao
nao usado em nenhum outro model do projeto ate aqui), calculada em
memoria a partir de quantidade_atual/estoque_minimo/estoque_maximo.

CORRECAO: ganhou is_deleted/deleted_at seguindo a skill 02 ("padrao
para qualquer entidade gerada pelo CrudGen") - a omissao original
quebrava a tela de listagem gerada (CrudGen filtra por is_deleted
incondicionalmente).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Saldo de Estoque")
@plural("saldos")
@required("material_id", message="Material é obrigatório")
class Saldo(db.Model):
    __tablename__ = "saldo"

    id = db.Column(db.Integer, primary_key=True)

    material_id = db.Column(db.Integer, db.ForeignKey("material.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    material = db.relationship("Material", backref=db.backref("saldo", uselist=False, lazy=True))

    quantidade_atual = db.Column(db.Float, nullable=False, default=0.0)
    custo_medio = db.Column(db.Float, nullable=True)
    valor_total_estoque = db.Column(db.Float, nullable=True)
    estoque_minimo = db.Column(db.Float, nullable=True)
    estoque_maximo = db.Column(db.Float, nullable=True)

    # Fase 4 (skill 23) - cache de última compra, alimentado por
    # estoque_service.receber_pedido_compra()
    ultimo_preco_compra = db.Column(db.Float, nullable=True)
    ultimo_fornecedor_id = db.Column(db.Integer, db.ForeignKey("fornecedor.id", ondelete="RESTRICT"), nullable=True)
    ultimo_fornecedor = db.relationship("Fornecedor")
    data_ultima_compra = db.Column(db.Date, nullable=True)

    ultima_atualizacao = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    @property
    def status(self) -> str:
        """Calculado em memória - não persistido. 'abaixo_minimo' /
        'acima_maximo' / 'normal', ou 'sem_referencia' se estoque_minimo/
        maximo não estiverem preenchidos."""
        if self.estoque_minimo is not None and self.quantidade_atual < self.estoque_minimo:
            return "abaixo_minimo"
        if self.estoque_maximo is not None and self.quantidade_atual > self.estoque_maximo:
            return "acima_maximo"
        if self.estoque_minimo is None and self.estoque_maximo is None:
            return "sem_referencia"
        return "normal"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "material_id": self.material_id,
            "quantidade_atual": self.quantidade_atual,
            "custo_medio": self.custo_medio,
            "valor_total_estoque": self.valor_total_estoque,
            "estoque_minimo": self.estoque_minimo,
            "estoque_maximo": self.estoque_maximo,
            "ultimo_preco_compra": self.ultimo_preco_compra,
            "ultimo_fornecedor_id": self.ultimo_fornecedor_id,
            "data_ultima_compra": self.data_ultima_compra.isoformat() if self.data_ultima_compra else None,
            "status": self.status,
            "ultima_atualizacao": self.ultima_atualizacao.isoformat() if self.ultima_atualizacao else None,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self) -> str:
        return f"<Saldo material_id={self.material_id} qtd={self.quantidade_atual}>"
