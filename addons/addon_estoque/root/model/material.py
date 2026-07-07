"""
addons/addon_estoque/root/model/material.py

Identidade generica de qualquer item estocavel (materia-prima,
embalagem, kit/composto). Nao conhece nenhum dominio de negocio
especifico - ver docs/skills/02-nomenclatura-tabelas-e-prefixos.md e
addons/addon_estoque/docs/technical/04-modelo-de-dados.md.

`nome` e unique=True porque e a chave de negocio usada por outros
Addons ao resolver referencia fraca (skill 02: nunca FK cross-Addon) -
mesmo padrao ja usado em DeviceFunction.name/get_function_by_name.

AMPLIACAO (sessao de cadastro fiscal/rastreio, ver BACKLOG.md): campos
novos sku/codigo_barras/descricao/fabricante_id/codigo_fabricante/
origem_id/tipo_produto_id/familia/subcategoria/ncm/cest/vida_util/
lote_controlado. O campo `categoria` (string livre) foi SUBSTITUIDO
por `categoria_id` (FK para Categoria) - decisao explicita, nao e
aditiva.

`origem_id` e `tipo_produto_id` sao obrigatorios (nullable=False) por
decisao de schema, mas o autocreate de feature_brew_father nao tem
essa informacao vinda da API do BrewFather - resolve via seeds fixos
(Origem "A definir", TipoProduto "Insumo", ver
services/estoque_seed.py) e marca `pendente_revisao=True`. Este flag
so sinaliza (filtro na tela de-para) - nunca bloqueia
Movimentacao/Saldo (decisao explicita, ver
addons/addon_brewstation/features/feature_brew_father/services/ingredient_autocreate_service.py).
`sku` segue o mesmo caminho: gerado automaticamente nesse fluxo, mas
sempre editavel depois.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length, display_field


@label("Material")
@plural("materials")
@display_field("nome")
@required("nome", message="Nome do material é obrigatório")
@required("sku", message="SKU do material é obrigatório")
@required("origem_id", message="Origem é obrigatória")
@required("tipo_produto_id", message="Tipo de produto é obrigatório")
@required("categoria_id", message="Categoria é obrigatória")
@max_length("nome", 200)
@max_length("sku", 60)
class Material(db.Model):
    __tablename__ = "material"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(200), unique=True, nullable=False)

    sku = db.Column(db.String(60), unique=True, nullable=False)
    codigo_barras = db.Column(db.String(50), nullable=True)
    descricao = db.Column(db.Text, nullable=True)

    fabricante_id = db.Column(db.Integer, db.ForeignKey("fabricante.id", ondelete="RESTRICT"), nullable=True, index=True)
    fabricante = db.relationship("Fabricante", backref=db.backref("materiais", lazy=True))
    codigo_fabricante = db.Column(db.String(60), nullable=True)

    origem_id = db.Column(db.Integer, db.ForeignKey("origem.id", ondelete="RESTRICT"), nullable=False, index=True)
    origem = db.relationship("Origem", backref=db.backref("materiais", lazy=True))

    tipo_produto_id = db.Column(db.Integer, db.ForeignKey("tipo_produto.id", ondelete="RESTRICT"), nullable=False, index=True)
    tipo_produto = db.relationship("TipoProduto", backref=db.backref("materiais", lazy=True))

    familia = db.Column(db.String(100), nullable=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria.id", ondelete="RESTRICT"), nullable=False, index=True)
    categoria = db.relationship("Categoria", backref=db.backref("materiais", lazy=True))
    subcategoria = db.Column(db.String(100), nullable=True)

    ncm = db.Column(db.String(20), nullable=True)
    cest = db.Column(db.String(20), nullable=True)
    vida_util = db.Column(db.Integer, nullable=True)  # dias
    lote_controlado = db.Column(db.Boolean, default=False, nullable=False)

    # True quando o registro foi criado via autocreate (feature_brew_father)
    # com origem_id/tipo_produto_id resolvidos por seed em vez de escolha
    # humana - sinaliza revisão pendente na tela de-para, nunca bloqueia
    # movimentação de estoque (decisão explícita desta sessão).
    pendente_revisao = db.Column(db.Boolean, default=False, nullable=False)

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
            "sku": self.sku,
            "codigo_barras": self.codigo_barras,
            "descricao": self.descricao,
            "fabricante_id": self.fabricante_id,
            "codigo_fabricante": self.codigo_fabricante,
            "origem_id": self.origem_id,
            "tipo_produto_id": self.tipo_produto_id,
            "familia": self.familia,
            "categoria_id": self.categoria_id,
            "subcategoria": self.subcategoria,
            "ncm": self.ncm,
            "cest": self.cest,
            "vida_util": self.vida_util,
            "lote_controlado": self.lote_controlado,
            "pendente_revisao": self.pendente_revisao,
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
        return f"<Material {self.nome} ({self.sku})>"
