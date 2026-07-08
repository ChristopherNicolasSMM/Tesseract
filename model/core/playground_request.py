"""
model/core/playground_request.py

tesseract_playground_request — histórico de requisições testadas no
API/SQL Playground (skill 06, Patch C + adenda "Playground v2", §8).
Core, não passa pelo CrudGen — mesma categoria de
ModelDefinition/CodeSnapshot (skill 00, Adendo Fase 7a).
"""
from datetime import datetime, timezone

from core.db import db


class PlaygroundRequestKind:
    HTTP = "http"
    SQL = "sql"

    ALL = (HTTP, SQL)


class PlaygroundAuthType:
    NONE = "none"
    BEARER = "bearer"
    BASIC = "basic"
    API_KEY = "api_key"

    ALL = (NONE, BEARER, BASIC, API_KEY)


class PlaygroundRequest(db.Model):
    __tablename__ = "tesseract_playground_request"

    id = db.Column(db.Integer, primary_key=True)

    kind = db.Column(db.String(10), nullable=False, default=PlaygroundRequestKind.HTTP)
    name = db.Column(db.String(150), nullable=True)

    # Campos de HTTP (kind=http)
    http_method = db.Column(db.String(10), nullable=True)
    url = db.Column(db.String(500), nullable=True)
    headers_json = db.Column(db.JSON, nullable=True)
    body_json = db.Column(db.JSON, nullable=True)

    # Playground v2 (skill 06 §8) — só relevante para kind=http
    params_json = db.Column(db.JSON, nullable=True)
    auth_type = db.Column(db.String(20), nullable=True, default=PlaygroundAuthType.NONE)
    auth_config = db.Column(db.JSON, nullable=True)

    # Playground v2 (skill 06 §8.2/§8.3) — organização do histórico
    folder_id = db.Column(db.Integer, db.ForeignKey("tesseract_playground_folder.id"), nullable=True)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)

    # Campo de SQL (kind=sql) — sempre SELECT, validado antes de executar
    # (skill 06 §6) — nunca persistimos um texto de SQL não-SELECT aqui.
    sql_text = db.Column(db.Text, nullable=True)

    last_response_json = db.Column(db.JSON, nullable=True)
    last_status_code = db.Column(db.Integer, nullable=True)
    last_error = db.Column(db.Text, nullable=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)
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
            "kind": self.kind,
            "name": self.name,
            "http_method": self.http_method,
            "url": self.url,
            "sql_text": self.sql_text,
            "folder_id": self.folder_id,
            "is_archived": self.is_archived,
            "auth_type": self.auth_type,
            "last_status_code": self.last_status_code,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<PlaygroundRequest {self.kind}:{self.name or self.id}>"
