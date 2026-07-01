"""
model/core/model_definition.py

tesseract_model_definition — rascunho/registro de um Model a ser (ou já)
gerado pelo Model Builder Visual (skill 06). Não passa pelo CrudGen —
é infraestrutura de Core escrita à mão, mesma categoria de
CodeSnapshot/Transaction (skill 00, Adendo Fase 7a).

Nesta fase (Patch A da skill 06) só os escopos "existing_addon" e
"existing_feature" têm geração implementada — "new_addon"/"new_feature"
ficam registrados no schema (para não quebrar quando o Patch B for
aplicado), mas o service rejeita a geração desses dois com uma
mensagem explícita até lá.
"""
from datetime import datetime, timezone

from core.db import db


class ModelDefinitionScope:
    NEW_ADDON = "new_addon"
    EXISTING_ADDON = "existing_addon"
    NEW_FEATURE = "new_feature"
    EXISTING_FEATURE = "existing_feature"

    ALL = (NEW_ADDON, EXISTING_ADDON, NEW_FEATURE, EXISTING_FEATURE)


class ModelDefinitionStatus:
    DRAFT = "draft"
    GENERATED = "generated"
    ERROR = "error"


class ModelDefinition(db.Model):
    __tablename__ = "tesseract_model_definition"

    id = db.Column(db.Integer, primary_key=True)

    target_scope = db.Column(db.String(20), nullable=False, default=ModelDefinitionScope.EXISTING_ADDON)
    target_addon_name = db.Column(db.String(100), nullable=False)
    target_feature_name = db.Column(db.String(100), nullable=True)

    model_name = db.Column(db.String(100), nullable=False)  # PascalCase
    table_short_name = db.Column(db.String(80), nullable=False)  # snake_case, sem prefixo

    # Campos ainda não confirmados de addon.json/feature.json (label,
    # description, table_prefix/table_prefix_suffix, env_keys) — só usado
    # quando target_scope é new_addon/new_feature (Patch B).
    manifest_draft_json = db.Column(db.JSON, nullable=True)

    status = db.Column(db.String(20), nullable=False, default=ModelDefinitionStatus.DRAFT)
    error_message = db.Column(db.Text, nullable=True)
    generated_at = db.Column(db.DateTime, nullable=True)
    generation_run_id = db.Column(db.String(36), nullable=True)
    migration_revision = db.Column(db.String(64), nullable=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    fields = db.relationship(
        "ModelFieldDefinition",
        backref="model_definition",
        cascade="all, delete-orphan",
        order_by="ModelFieldDefinition.order_index",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "target_scope": self.target_scope,
            "target_addon_name": self.target_addon_name,
            "target_feature_name": self.target_feature_name,
            "model_name": self.model_name,
            "table_short_name": self.table_short_name,
            "status": self.status,
            "error_message": self.error_message,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<ModelDefinition {self.model_name} ({self.status})>"
