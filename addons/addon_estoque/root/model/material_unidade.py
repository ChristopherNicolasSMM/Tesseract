"""
addons/addon_estoque/root/model/material_unidade.py

Fase 2 (skill 23) — permite múltiplas unidades por Material, com fator
de conversão para uma unidade-base única (ex.: Material "Malte Pilsen"
comprado em `saco25kg`, consumido/movimentado em `kg`).

`Saldo.quantidade_atual` e `Movimentacao.quantidade` continuam SEMPRE
na unidade-base do Material — a conversão acontece uma única vez, na
entrada do dado (serviço de compra/movimentação), nunca no ledger em
si. Isso preserva `Movimentacao` como ledger imutável sem ambiguidade
de unidade entre linhas (ver docs/skills/23-proposta-expansao-addon-estoque.md,
seção 3).

`is_unidade_base`: exatamente um `true` por `material_id` — imposto
por índice único parcial (não por `unique=True` na coluna, que criaria
uma constraint cheia incompatível com múltiplas linhas `false`), mesmo
padrão já usado em `YeastBankConfig`
(addons/addon_brewstation/features/feature_yeast_bank/model/yeast_bank_config.py).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, enum_field, field_labels


@label("Unidade de Material")
@plural("material_unidades")
@required("material_id", message="Material é obrigatório")
@required("unidade", message="Unidade é obrigatória")
@required("fator_para_base", message="Fator de conversão para a unidade-base é obrigatório")
@enum_field("tipo_uso", options=[
    ("compra", "Compra"), ("consumo", "Consumo"), ("ambos", "Ambos"),
])
@field_labels({
    "material_id": "Material",
    "unidade": "Unidade",
    "fator_para_base": "Fator para Unidade-Base",
    "is_unidade_base": "É a Unidade-Base?",
    "tipo_uso": "Tipo de Uso",
    "ativo": "Ativo",
})
class MaterialUnidade(db.Model):
    __tablename__ = "material_unidade"

    __table_args__ = (
        db.Index(
            "uq_material_unidade_base_por_material", "material_id",
            unique=True, sqlite_where=db.text("is_unidade_base = 1 AND is_deleted = 0"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    material_id = db.Column(db.Integer, db.ForeignKey("material.id", ondelete="CASCADE"), nullable=False, index=True)
    material = db.relationship("Material", backref=db.backref("unidades", lazy=True))

    # Livre por enquanto (não é lookup) — baixo volume de valores
    # distintos por Material, não justifica tabela própria nesta fase
    # (ver skill 23, seção 3). Ex.: "kg", "saco25kg", "caixa12un".
    unidade = db.Column(db.String(20), nullable=False)

    # Quantas unidades-base equivalem a 1 desta unidade. A
    # unidade-base tem fator_para_base = 1.0 por definição.
    fator_para_base = db.Column(db.Float, nullable=False, default=1.0)

    # unique=True NÃO fica na coluna — unicidade real é o índice
    # parcial em __table_args__ (só is_unidade_base=1 AND is_deleted=0),
    # senão nunca seria possível ter mais de uma unidade não-base por
    # Material. Ver nota do módulo.
    is_unidade_base = db.Column(db.Boolean, default=False, nullable=False)

    tipo_uso = db.Column(db.String(20), nullable=False, default="ambos")  # compra | consumo | ambos

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
            "material_id": self.material_id,
            "unidade": self.unidade,
            "fator_para_base": self.fator_para_base,
            "is_unidade_base": self.is_unidade_base,
            "tipo_uso": self.tipo_uso,
            "ativo": self.ativo,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<MaterialUnidade material_id={self.material_id} unidade={self.unidade} fator={self.fator_para_base}>"
