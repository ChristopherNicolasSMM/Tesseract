"""
model/core/code_snapshot.py

tesseract_code_snapshot — histórico versionado de arquivos do projeto
(gerados pelo CrudGen, Fase 4, ou editados manualmente). Cada linha é
uma versão COMPLETA e independente do conteúdo — não é diff
incremental, é o texto inteiro, para que diff visual e restauração
nunca dependam de reconstruir histórico a partir de patches.

Portado do PyTeca quase 1:1 (model/core/admin/code_snapshot.py).
"""
from datetime import datetime, timezone

from core.db import db


class SnapshotOrigin:
    """Origem que disparou a criação do snapshot."""
    GENERATED = "generated"           # gravado pelo CrudGen (.j2 -> arquivo)
    MANUAL_EDIT = "manual_edit"       # editado via futura IDE interna
    RESTORE = "restore"               # restauração de uma versão anterior
    PRE_OVERWRITE = "pre_overwrite"   # snapshot do conteúdo ANTES de ser sobrescrito


class CodeSnapshot(db.Model):
    __tablename__ = "tesseract_code_snapshot"

    id = db.Column(db.Integer, primary_key=True)

    file_path = db.Column(db.String(500), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    content_hash = db.Column(db.String(64), nullable=False, index=True)  # sha256
    size_bytes = db.Column(db.Integer, nullable=False, default=0)

    origin = db.Column(db.String(20), nullable=False, default=SnapshotOrigin.GENERATED)
    triggered_by = db.Column(db.String(120), nullable=True)  # "cli:generate", "ui:model_builder"
    model_name = db.Column(db.String(100), nullable=True, index=True)

    # Agrupa todos os arquivos escritos numa mesma execução de generate().
    generation_run_id = db.Column(db.String(36), nullable=True, index=True)

    # É a versão atualmente presente no disco para este file_path? Mantido
    # em sincronia pela camada de versionamento — nunca calculado via
    # leitura de disco em runtime, pra tela de histórico ser barata.
    is_current = db.Column(db.Boolean, nullable=False, default=True, index=True)

    # De qual snapshot este partiu — monta uma linha do tempo real
    # (A -> B -> C), não só uma lista cronológica solta.
    parent_snapshot_id = db.Column(
        db.Integer, db.ForeignKey("tesseract_code_snapshot.id"), nullable=True
    )

    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    created_by_user_id = db.Column(
        db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True
    )

    __table_args__ = (
        db.Index("ix_tesseract_snapshot_path_created", "file_path", "created_at"),
        db.Index("ix_tesseract_snapshot_path_current", "file_path", "is_current"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "content_hash": self.content_hash,
            "size_bytes": self.size_bytes,
            "origin": self.origin,
            "triggered_by": self.triggered_by,
            "model_name": self.model_name,
            "generation_run_id": self.generation_run_id,
            "is_current": self.is_current,
            "parent_snapshot_id": self.parent_snapshot_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by_user_id": self.created_by_user_id,
        }

    def __repr__(self) -> str:
        return f"<CodeSnapshot id={self.id} file={self.file_path} hash={self.content_hash[:8]}>"
