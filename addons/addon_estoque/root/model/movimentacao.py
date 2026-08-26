"""
addons/addon_estoque/root/model/movimentacao.py

Ledger de movimentacao de estoque - imutavel na pratica (correcao de
lancamento errado e sempre um NOVO registro, tipo_movimentacao="ajuste",
nunca UPDATE de quantidade/custo de um lancamento existente).

CORRECAO (pos-bug real, ver commit): ganhou is_deleted/deleted_at
seguindo a skill 02 ("padrao para qualquer entidade gerada pelo
CrudGen") - a omissao original quebrava a tela de listagem (CrudGen
gera .filter(Model.is_deleted...) incondicionalmente). A trash/restore
gerada pelo CrudGen fica disponivel na UI, mas o uso pretendido
continua sendo so para esconder um lancamento claramente errado da
listagem - nunca para "consertar" um valor errado (isso e sempre um
novo lancamento de ajuste). Se isso for um problema na pratica,
avaliar esconder as acoes trash/restore via hook do controller.

AMPLIACAO (skill 23, Fase 4): rastro de compra - todas as colunas
novas sao nullable, movimentacoes manuais (ajuste, ou entrada sem
passar por PedidoCompra) continuam validas sem preencher nada disso.
`quantidade` continua SEMPRE na unidade-base do Material (regra de
ouro da Fase 2) - unidade_original/quantidade_original/
fator_conversao_aplicado sao so para auditoria, nunca lidos pelo
calculo de saldo.
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

    # Fase 4 (skill 23) - rastro de compra, tudo opcional
    fornecedor_id = db.Column(db.Integer, db.ForeignKey("fornecedor.id", ondelete="RESTRICT"), nullable=True, index=True)
    fornecedor = db.relationship("Fornecedor")
    pedido_compra_item_id = db.Column(db.Integer, db.ForeignKey("item_pedido_compra.id", ondelete="RESTRICT"), nullable=True, index=True)
    pedido_compra_item = db.relationship("ItemPedidoCompra")
    unidade_original = db.Column(db.String(20), nullable=True)
    quantidade_original = db.Column(db.Float, nullable=True)
    fator_conversao_aplicado = db.Column(db.Float, nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

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
            "fornecedor_id": self.fornecedor_id,
            "pedido_compra_item_id": self.pedido_compra_item_id,
            "unidade_original": self.unidade_original,
            "quantidade_original": self.quantidade_original,
            "fator_conversao_aplicado": self.fator_conversao_aplicado,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Movimentacao {self.tipo_movimentacao} material_id={self.material_id} qtd={self.quantidade}>"
