"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_bank_event.py

Ponto de entrada único da linha do tempo do Yeast Bank (skill 21).
Todo evento nasce aqui — quando o tipo exige campos especializados
(Starter, Contagem de Células), o próprio fluxo de criação
(controller hook `post_create_redirect`) cria o registro na tabela
especializada e redireciona pra lá. `starter_id`/`cell_count_id` são
preenchidos só por esse fluxo — nunca escolhidos manualmente
(`@readonly_fields`).

Reanálise (2026-08-24): evento tipo "Descarte" agora aplica a
transição de verdade no `YeastBankItem` vinculado — `status_before`
captura o status atual do item automaticamente (também
`@readonly_fields`), `status_after` é escolhido pela pessoa
(Descartado/Contaminado) e é aplicado ao item pelo mesmo hook.
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
@readonly_fields(["starter_id", "cell_count_id", "status_before"])
@field_labels({
    "bank_item_id": "Item do Banco",
    "event_type": "Tipo do Evento",
    "starter_id": "Starter Gerado",
    "cell_count_id": "Contagem Gerada",
    "status_before": "Status Anterior (automático)",
    "status_after": "Status Posterior",
    "notes": "Observações",
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

    # Preenchidos só pelo fluxo automático de criação (post_create_redirect,
    # controller hook) — nunca escolhidos manualmente (@readonly_fields acima).
    starter_id = db.Column(db.Integer, db.ForeignKey("starter_log.id"), nullable=True)
    starter = db.relationship("YeastStarterLog", backref=db.backref("events", lazy=True))

    cell_count_id = db.Column(db.Integer, db.ForeignKey("cell_count_history.id"), nullable=True)
    cell_count = db.relationship("YeastCellCountHistory", backref=db.backref("events", lazy=True))

    status_before = db.Column(db.String(30), nullable=True)
    status_after = db.Column(db.String(30), nullable=True)
    notes = db.Column(db.Text, nullable=True)

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
            "starter_id": self.starter_id,
            "cell_count_id": self.cell_count_id,
            "status_before": self.status_before,
            "status_after": self.status_after,
            "notes": self.notes,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<YeastBankEvent id={self.id} event_type={self.event_type}>"
