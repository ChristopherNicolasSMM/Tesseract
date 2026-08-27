"""
addons/addon_estoque/root/model/endereco.py

Fase 3 (skill 23) — endereço reutilizável, dado puro, sem saber quem é
o dono (mesmo papel que User já tem em relação a outras entidades).
Quem vincula é uma tabela própria por entidade dona (FornecedorEndereco,
TransportadoraEndereco - ver esses models) - decisão explícita de NÃO
usar padrão polimórfico (entidade_tipo + entidade_id sem FK real),
porque o projeto nunca usa esse padrão em lugar nenhum (investigado em
model/core/associations.py e Composicao antes de decidir - ver skill
23, seção 5).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length, display_field


@display_field("logradouro")
@label("Endereço")
@plural("enderecos")
@required("logradouro", message="Logradouro é obrigatório")
@required("cidade", message="Cidade é obrigatória")
@required("estado", message="Estado (UF) é obrigatório")
@max_length("logradouro", 200)
@max_length("numero", 20)
@max_length("complemento", 100)
@max_length("bairro", 100)
@max_length("cidade", 100)
@max_length("estado", 2)
@max_length("pais", 60)
@max_length("cep", 15)
@max_length("ponto_referencia", 200)
@max_length("descricao", 150)
class Endereco(db.Model):
    __tablename__ = "endereco"

    id = db.Column(db.Integer, primary_key=True)

    logradouro = db.Column(db.String(200), nullable=False)
    numero = db.Column(db.String(20), nullable=True)
    complemento = db.Column(db.String(100), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    cidade = db.Column(db.String(100), nullable=False)
    estado = db.Column(db.String(2), nullable=False)  # UF
    pais = db.Column(db.String(60), nullable=False, default="Brasil")
    cep = db.Column(db.String(15), nullable=True)
    ponto_referencia = db.Column(db.String(200), nullable=True)
    descricao = db.Column(db.String(150), nullable=True)  # ex.: "Depósito 2", livre

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
            "logradouro": self.logradouro,
            "numero": self.numero,
            "complemento": self.complemento,
            "bairro": self.bairro,
            "cidade": self.cidade,
            "estado": self.estado,
            "pais": self.pais,
            "cep": self.cep,
            "ponto_referencia": self.ponto_referencia,
            "descricao": self.descricao,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Endereco {self.logradouro}, {self.cidade}/{self.estado}>"
