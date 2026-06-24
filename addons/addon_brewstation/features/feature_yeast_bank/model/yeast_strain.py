"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_strain.py

Cepa base (identidade da levedura) — portado de
plugin_yeast_bank/model/yeast_bank_models.py (BrewStation).

A cepa representa a "família/raça" da levedura. Ela não é a amostra
física; as amostras físicas (YeastBankItem) e o restante das tabelas
de yeast_bank (item físico, starter, storage device/reading, config,
histórico de contagem, eventos) ficam para a próxima leva de migração
(BACKLOG.md, Fase 5b) — esta primeira fatia prova o pipeline
Addon+Feature+ModuleManager+CrudGen ponta a ponta com a entidade mais
central e mais simples de yeast_bank.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length, permission, choices


@label("Cepa de Levedura")
@plural("yeast_strains")
@choices("status", label="Status")
@required("name", message="Nome da cepa é obrigatório")
@max_length("name", 200)
@permission(
    "recalculate_viability",
    description="Recalcular viabilidade estimada da cepa",
)
class YeastStrain(db.Model):
    __tablename__ = "strain"  # nome curto — CrudGen/ModuleManager aplicam o prefixo

    id = db.Column(db.Integer, primary_key=True)

    code = db.Column(db.String(64), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    family = db.Column(db.String(50), nullable=True)
    supplier = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Estado estratégico da cepa (não confundir com is_deleted do item físico).
    status = db.Column(db.String(30), nullable=False, default="active")

    # Parâmetros de viabilidade por cepa — usados para estimar a
    # viabilidade dos itens do banco ao longo do tempo.
    viability_model = db.Column(db.String(50), nullable=False, default="linear_decay_default")
    daily_viability_loss_pct = db.Column(db.Float, nullable=True, default=0.35)
    viability_correction_factor = db.Column(db.Float, nullable=True, default=1.0)
    initial_reference_viability_pct = db.Column(db.Float, nullable=True, default=95.0)
    viability_floor_pct = db.Column(db.Float, nullable=True, default=0.0)
    viability_notes = db.Column(db.Text, nullable=True)

    # Soft-delete (skill 02) — substitui o uso de "status" para isso,
    # que no BrewStation original fazia ambas as coisas.
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
            "code": self.code,
            "name": self.name,
            "family": self.family,
            "supplier": self.supplier,
            "notes": self.notes,
            "status": self.status,
            "viability_model": self.viability_model,
            "daily_viability_loss_pct": self.daily_viability_loss_pct,
            "viability_correction_factor": self.viability_correction_factor,
            "initial_reference_viability_pct": self.initial_reference_viability_pct,
            "viability_floor_pct": self.viability_floor_pct,
            "viability_notes": self.viability_notes,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<YeastStrain {self.name}>"
