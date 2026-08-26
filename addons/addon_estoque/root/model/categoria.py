"""
addons/addon_estoque/root/model/categoria.py

Lookup simples - decisão de sessão anterior (ampliação de Material,
item 1 do escopo). SUBSTITUI o campo Material.categoria (string livre)
por FK - a distinção materia_prima/embalagem/kit/outro que existia
antes vira dado de tabela em vez de valor fixo em código, mesmo padrão
de Fabricante/Origem/TipoProduto.

AMPLIACAO (skill 23, Fase 1 - resolucao da sobreposicao Categoria x
TipoProduto): TipoProduto passa a ser o eixo de NATUREZA do Material
(Insumo/Embalagem/Produto Acabado/Peca/Uso e Consumo); Categoria passa
a ser a classificacao FINA dentro desse tipo (ex.: Categoria "Malte"
com tipo_produto_id apontando pra "Insumo"). `tipo_produto_id` e
nullable de proposito - Categorias ja cadastradas ficam sem
classificacao ate revisao manual, mesmo espirito do
`Material.pendente_revisao` (nunca bloqueia uso da Categoria
existente). Ver docs/skills/23-proposta-expansao-addon-estoque.md.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length


@label("Categoria")
@plural("categorias")
@required("descricao", message="Descricao da categoria é obrigatório")
@max_length("descricao", 100)
class Categoria(db.Model):
    __tablename__ = "categoria"

    id = db.Column(db.Integer, primary_key=True)

    descricao = db.Column(db.String(100), unique=True, nullable=False)
    codigo = db.Column(db.String(20), unique=True, nullable=False)

    tipo_produto_id = db.Column(
        db.Integer,
        db.ForeignKey("tipo_produto.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    tipo_produto = db.relationship(
        "TipoProduto", backref=db.backref("categorias", lazy=True),
    )

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
            "descricao" : self.descricao,
            "codigo"    : self.codigo,
            "tipo_produto_id": self.tipo_produto_id,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Categoria {self.descricao}>"
