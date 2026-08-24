"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_bank_config.py

Configuração por tipo de armazenamento — 1 linha por `storage_type`
(constraint UNIQUE), com o % de decaimento diário, prazo de validade e
os dois limites de alerta de baixa viabilidade daquele tipo.

Redesenhado em 2026-08-21 (decisão do Christopher): a versão anterior
tinha 4 campos de validade (`expiry_master_days`/`expiry_work_days`/
`expiry_plate_days`/`expiry_saline_days`) numa mesma linha de
`storage_type`, sem nenhum consumidor real (achado da auditoria de
campos, BACKLOG Fase 18) — substituídos por um único `expiry_days`.
`daily_viability_loss_pct` desta config SUBSTITUI o da `YeastStrain`
quando presente (não combina) — ver `viability_engine.recalculate_all()`.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, enum_field, required, field_labels


@label("Configuração do Banco de Levedura")
@plural("yeast_bank_configs")
@required("storage_type", message="Tipo de armazenamento é obrigatório")
@enum_field("storage_type", options=["Agar Inclinado", "Óleo", "Agar Inc. + Óleo" , "Solu. NaCl 0.9%", "Gligerina", "Seca","Lama"])
@field_labels({
    "storage_type": "Tipo de Armazenamento",
    "daily_viability_loss_pct": "Perda de Viabilidade Diária (%)",
    "expiry_days": "Prazo de Validade (dias)",
    "alert_days_before_expiry": "Alerta — Dias Antes de Vencer",
    "alert_min_viability_pct": "Alerta — Viabilidade Mínima (%)",
})
class YeastBankConfig(db.Model):
    __tablename__ = "bank_config"

    __table_args__ = (
        db.Index(
            "uq_bank_config_storage_type_ativo", "storage_type",
            unique=True, sqlite_where=db.text("is_deleted = 0"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    # unique=True NÃO fica na declaração da coluna de propósito: a
    # unicidade real é um ÍNDICE PARCIAL (só is_deleted=0), criado na
    # migration 0b8fa81614a6 — soft-delete precisa disso, senão uma
    # linha na lixeira colidiria pra sempre com uma nova do mesmo
    # tipo. Column(unique=True) geraria uma constraint cheia (sem
    # partial), incompatível com isso — e faria `flask db migrate`
    # detectar diff falso pra sempre tentando "consertar".
    storage_type = db.Column(db.String(40), nullable=False)

    daily_viability_loss_pct = db.Column(db.Float, nullable=True)
    expiry_days = db.Column(db.Integer, nullable=True)

    # Alerta de baixa viabilidade — os dois são independentes e
    # opcionais; quando cadastrados, QUALQUER um dos dois disparando
    # já conta como alerta (decisão do Christopher, 2026-08-21). A
    # lógica de disparo/notificação em si é fase própria (BACKLOG,
    # reanálise de YeastBankEvent/YeastStorageReading) — esta config
    # só guarda os limites.
    alert_days_before_expiry = db.Column(db.Integer, nullable=True)
    alert_min_viability_pct = db.Column(db.Float, nullable=True)

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
            "storage_type": self.storage_type,
            "daily_viability_loss_pct": self.daily_viability_loss_pct,
            "expiry_days": self.expiry_days,
            "alert_days_before_expiry": self.alert_days_before_expiry,
            "alert_min_viability_pct": self.alert_min_viability_pct,
            "is_deleted": self.is_deleted,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<YeastBankConfig storage_type={self.storage_type}>"
