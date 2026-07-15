"""
addons/addon_brewstation/features/feature_brew_father/model/brew_father_sync.py

Log de sincronizacao - unica tabela de dominio propria desta Feature
(decisao desta sessao: Receita/Lote nao sao duplicados aqui, moram em
feature_mash_control com origem_receita="BrewFather"). Ver
docs/technical/04-modelo-de-dados.md.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, choices, enum_field


@label("Sincronização BrewFather")
@plural("brewfather_syncs")
@enum_field("status", options=["em_andamento", "sucesso", "erro", "parcial"])
@choices("tipo_sync", label="Tipo")
@choices("status", label="Status")
@required("tipo_sync", message="Tipo de sincronização é obrigatório")
class BrewFatherSync(db.Model):
    __tablename__ = "sync"  # nome curto — prefixo do CrudGen já adiciona "brewfather_" (evita "..._brewfather_brewfather_sync")

    id = db.Column(db.Integer, primary_key=True)

    tipo_sync = db.Column(db.String(20), nullable=False)  # recipes, batches, inventory, all
    status = db.Column(db.String(20), nullable=False, default="em_andamento")  # em_andamento, sucesso, erro, parcial
    quantidade_processada = db.Column(db.Integer, nullable=False, default=0)
    quantidade_erro = db.Column(db.Integer, nullable=False, default=0)
    raw_data = db.Column(db.Text, nullable=True)  # JSON bruto, só auditoria/debug
    mensagem_erro = db.Column(db.Text, nullable=True)

    iniciado_em = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    finalizado_em = db.Column(db.DateTime, nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo_sync": self.tipo_sync,
            "status": self.status,
            "quantidade_processada": self.quantidade_processada,
            "quantidade_erro": self.quantidade_erro,
            "mensagem_erro": self.mensagem_erro,
            "iniciado_em": self.iniciado_em.isoformat() if self.iniciado_em else None,
            "finalizado_em": self.finalizado_em.isoformat() if self.finalizado_em else None,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self) -> str:
        return f"<BrewFatherSync {self.tipo_sync} status={self.status}>"
