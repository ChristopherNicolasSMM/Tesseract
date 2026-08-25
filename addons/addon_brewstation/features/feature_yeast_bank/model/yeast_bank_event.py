"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_bank_event.py

Ponto de entrada único da linha do tempo do Yeast Bank (skill 21).
Todo evento nasce aqui — quando o tipo exige campos especializados,
o próprio fluxo de criação (controller hook `post_create_redirect`)
resolve o que precisa acontecer.

Skill 22 (2026-08-24): `YeastStarterLog` foi removida e fundida
diretamente aqui — os campos abaixo marcados "só Starter" só fazem
sentido quando `event_type="Starter"`, preenchidos no próprio
formulário do evento, sem redirecionar pra tela nenhuma (diferente de
"Contagem de Células", que continua criando `YeastCellCountHistory`
e redirecionando — ver skill 22, seção 2, pro porquê da assimetria).

`starter_status` e não `status`: `status_before`/`status_after` já
existem aqui pra outra coisa (transição do Item quando o evento é
Descarte) — reaproveitar o nome colidiria semanticamente com o fluxo
de propagação do Starter em si.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, enum_field, field_labels, readonly_fields, weak_ref


@label("Evento do Banco")
@plural("yeast_bank_events")
@required("event_type", message="Tipo do evento é obrigatório")
@required("bank_item_id", message="Item do banco é obrigatório")
@enum_field("event_type", options=["Starter", "Contagem de Células", "Descarte", "Outro"])
@enum_field("status_after", options=[("active", "Ativo"), ("discarded", "Descartado"), ("contaminated", "Contaminado")])
@enum_field("starter_status", options=["planned", "active", "completed", "discarded"])
@readonly_fields(["cell_count_id", "status_before"])
@field_labels({
    "bank_item_id": "Item do Banco",
    "event_type": "Tipo do Evento",
    "cell_count_id": "Contagem Gerada",
    "status_before": "Status Anterior (automático)",
    "status_after": "Status Posterior",
    "notes": "Observações",
    "brew_date": "Data da Brassagem",
    "start_date": "Data de Início",
    "target_volume_l": "Volume Alvo (L)",
    "objective": "Objetivo",
    "starter_status": "Status do Starter",
    "result_viability_percent": "Viabilidade Resultante (%)",
    "contamination_detected": "Contaminação Detectada",
    "estimated_cells_per_ml": "Estimativa de Células/mL",
})
@weak_ref("bank_item_id",
    resolver=("addons.addon_brewstation.features.feature_yeast_bank.services.yeast_reference_lookup.get_yeast_bank_item"),
    options="yeast_bank_items")
class YeastBankEvent(db.Model):
    __tablename__ = "bank_event"

    id = db.Column(db.Integer, primary_key=True)

    bank_item_id = db.Column(db.Integer, db.ForeignKey("bank_item.id"), nullable=False)
    bank_item = db.relationship("YeastBankItem", backref=db.backref("events", lazy=True))

    event_type = db.Column(db.String(50), nullable=False)

    # Preenchido só pelo fluxo automático de criação (post_create_redirect,
    # controller hook) — nunca escolhido manualmente (@readonly_fields acima).
    cell_count_id = db.Column(db.Integer, db.ForeignKey("cell_count_history.id"), nullable=True)
    # foreign_keys explícito: desde que YeastCellCountHistory ganhou
    # bank_event_id (skill 22), existem 2 caminhos de FK entre as duas
    # tabelas (este cell_count_id, e o bank_event_id do outro lado) —
    # sem isso, SQLAlchemy não sabe qual usar nesse relationship.
    cell_count = db.relationship(
        "YeastCellCountHistory",
        foreign_keys=[cell_count_id],
        backref=db.backref("events", lazy=True),
    )

    status_before = db.Column(db.String(30), nullable=True)
    status_after = db.Column(db.String(30), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # ── Campos vindos de YeastStarterLog (skill 22) — só fazem
    # sentido quando event_type="Starter", mas ficam sempre presentes
    # na tabela (mesmo padrão de qualquer campo opcional do CrudGen).
    brew_date = db.Column(db.Date, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    target_volume_l = db.Column(db.Float, nullable=True)
    objective = db.Column(db.String(30), nullable=True)
    starter_status = db.Column(db.String(30), nullable=True)
    result_viability_percent = db.Column(db.Float, nullable=True)
    contamination_detected = db.Column(db.Boolean, nullable=False, default=False)
    estimated_cells_per_ml = db.Column(db.Float, nullable=True)

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
            "bank_item_id": self.bank_item_id,
            "bank_item": self.bank_item.to_dict() if self.bank_item else None,
            "event_type": self.event_type,
            "cell_count_id": self.cell_count_id,
            "status_before": self.status_before,
            "status_after": self.status_after,
            "notes": self.notes,
            "brew_date": self.brew_date.isoformat() if self.brew_date else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "target_volume_l": self.target_volume_l,
            "objective": self.objective,
            "starter_status": self.starter_status,
            "result_viability_percent": self.result_viability_percent,
            "contamination_detected": bool(self.contamination_detected),
            "estimated_cells_per_ml": self.estimated_cells_per_ml,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<YeastBankEvent id={self.id} event_type={self.event_type}>"
