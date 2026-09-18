"""
addons/addon_brewstation/features/feature_envase/model/calculo_precificacao.py

Cálculo de precificação de um Lote (BrewSession) -> Envase. Fluxo
simula -> calcula -> cria Envase (proposta-precificacao-envase.md):
`envase_id` fica nullable de propósito, pra permitir simular preço
ANTES de criar o Envase (o legado do BrewStation, GitHub, também
permite isso via `envase_id` nullable em `calculo_envase`).

`lote_id` é FK real cross-Feature dentro do mesmo Addon (skill 02,
mesmo padrão de envase.lote_id).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, min_value, weak_ref

_MC = "addons.addon_brewstation.features.feature_mash_control.services.mash_control_lookups"


@label("Cálculo de Precificação")
@plural("calculo_precificacaos")
@required("lote_id", message="Lote é obrigatório")
@min_value("percentual_lucro", 0, message="Percentual de lucro não pode ser negativo")
@min_value("percentual_ipi", 0, message="Percentual de IPI não pode ser negativo")
@min_value("percentual_icms", 0, message="Percentual de ICMS não pode ser negativo")
@weak_ref("lote_id", resolver=f"{_MC}.get_session", options="brew_sessions")
@weak_ref("envase_id",
          resolver="addons.addon_brewstation.features.feature_envase.services.envase_lookup.get_envase",
          options="envases")
class CalculoPrecificacao(db.Model):
    __tablename__ = "calculo_precificacao"

    id = db.Column(db.Integer, primary_key=True)

    lote_id = db.Column(db.Integer, db.ForeignKey("session.id"), nullable=False, index=True)
    lote = db.relationship("BrewSession", backref=db.backref("calculos_precificacao", lazy=True))

    # Nullable de propósito — simulação antes de decidir criar o
    # Envase (envase_id só é preenchido quando o usuário confirma).
    envase_id = db.Column(db.Integer, db.ForeignKey("envase.id"), nullable=True, index=True)
    envase = db.relationship("Envase", backref=db.backref("calculos_precificacao", lazy=True))

    custo_ingredientes_total = db.Column(db.Float, nullable=False, default=0.0)
    custo_embalagem_total = db.Column(db.Float, nullable=False, default=0.0)
    subtotal = db.Column(db.Float, nullable=False, default=0.0)

    percentual_lucro = db.Column(db.Float, nullable=False, default=0.0)
    valor_lucro = db.Column(db.Float, nullable=False, default=0.0)

    percentual_ipi = db.Column(db.Float, nullable=False, default=0.0)
    valor_ipi = db.Column(db.Float, nullable=False, default=0.0)
    percentual_icms = db.Column(db.Float, nullable=False, default=0.0)
    valor_icms = db.Column(db.Float, nullable=False, default=0.0)

    valor_total = db.Column(db.Float, nullable=False, default=0.0)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "lote_id": self.lote_id,
            "envase_id": self.envase_id,
            "custo_ingredientes_total": self.custo_ingredientes_total,
            "custo_embalagem_total": self.custo_embalagem_total,
            "subtotal": self.subtotal,
            "percentual_lucro": self.percentual_lucro,
            "valor_lucro": self.valor_lucro,
            "percentual_ipi": self.percentual_ipi,
            "valor_ipi": self.valor_ipi,
            "percentual_icms": self.percentual_icms,
            "valor_icms": self.valor_icms,
            "valor_total": self.valor_total,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<CalculoPrecificacao lote_id={self.lote_id} valor_total={self.valor_total}>"
