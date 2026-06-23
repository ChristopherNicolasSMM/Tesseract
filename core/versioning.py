"""
core/versioning.py

Ponto único de decisão sobre QUANDO versionar (consulta ConfigService,
chaves versioning.*) e COMO versionar (grava CodeSnapshot, mantém
is_current em sincronia, agrupa por generation_run_id).

Nesta fase, sem CrudGen ainda (Fase 4), nada chama snapshot_if_needed()
automaticamente — a infraestrutura existe e está testada, pronta para
ser plugada em utils/generate_from_model._write_file() quando o
CrudGen existir. Portado do PyTeca quase 1:1.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

from core.db import db
from core.config_service import ConfigService
from model.core.code_snapshot import CodeSnapshot, SnapshotOrigin

logger = logging.getLogger(__name__)

# Contexto da execução atual (thread-safe, sem estado de módulo global).
# Definido uma vez no início de uma "run" de geração e lido por todo
# write subsequente daquela mesma execução.
_current_run_id: ContextVar[Optional[str]] = ContextVar("_current_run_id", default=None)
_current_model_name: ContextVar[Optional[str]] = ContextVar("_current_model_name", default=None)
_current_triggered_by: ContextVar[Optional[str]] = ContextVar("_current_triggered_by", default=None)


def start_generation_run(model_name: str | None, triggered_by: str = "cli:generate") -> str:
    """
    Marca o início de uma execução de geração. Todos os arquivos
    escritos até o próximo start_generation_run() compartilham o mesmo
    generation_run_id — agrupa "N arquivos gerados juntos" numa única
    entrada de histórico.
    """
    run_id = str(uuid.uuid4())
    _current_run_id.set(run_id)
    _current_model_name.set(model_name)
    _current_triggered_by.set(triggered_by)
    logger.debug(
        "Generation run iniciada: %s (model=%s, triggered_by=%s)",
        run_id, model_name, triggered_by,
    )
    return run_id


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def snapshot_if_needed(
    file_path: str,
    new_content: str,
    *,
    origin: str = SnapshotOrigin.GENERATED,
    created_by_user_id: int | None = None,
) -> CodeSnapshot | None:
    """
    Decide, com base em system_config (versioning.*), se deve versionar
    esta escrita, e grava se aplicável.

    Captura de edição manual perdida: antes de decidir sobre o novo
    conteúdo, lê o conteúdo ATUAL do disco (se o arquivo já existir) e,
    se divergir do último snapshot conhecido, captura essa versão
    primeiro (origin=PRE_OVERWRITE) — preservando uma edição manual no
    histórico antes de ela ser sobrescrita por uma nova geração.

    Retorna o CodeSnapshot do novo conteúdo, ou None se nada foi
    versionado (trigger desabilitado, ou on_diff sem alteração real).
    """
    if not ConfigService.get("versioning.enabled", default=True):
        logger.debug("Versionamento desabilitado (versioning.enabled=false).")
        return None

    trigger = ConfigService.get("versioning.trigger", default="on_diff")
    if trigger == "manual_only":
        logger.debug("Trigger=manual_only — escrita de %s não versionada automaticamente.", file_path)
        return None

    last = (
        CodeSnapshot.query
        .filter_by(file_path=file_path, is_current=True)
        .order_by(CodeSnapshot.created_at.desc())
        .first()
    )

    disk_path = Path(file_path)
    if disk_path.exists():
        try:
            disk_content = disk_path.read_text(encoding="utf-8")
            disk_hash = _sha256(disk_content)
            if last is None or last.content_hash != disk_hash:
                logger.debug(
                    "Disco diverge do último snapshot conhecido para %s — "
                    "capturando como PRE_OVERWRITE antes de prosseguir.",
                    file_path,
                )
                if last is not None:
                    last.is_current = False
                manual_snap = CodeSnapshot(
                    file_path=file_path,
                    content=disk_content,
                    content_hash=disk_hash,
                    size_bytes=len(disk_content.encode("utf-8")),
                    origin=SnapshotOrigin.PRE_OVERWRITE,
                    triggered_by="auto:pre_overwrite_capture",
                    generation_run_id=_current_run_id.get(),
                    is_current=True,
                    parent_snapshot_id=last.id if last is not None else None,
                )
                db.session.add(manual_snap)
                db.session.commit()
                last = manual_snap
        except (UnicodeDecodeError, OSError):
            logger.debug("Arquivo %s binário/ilegível — não tentando versionar o disco.", file_path)

    new_hash = _sha256(new_content)

    if trigger == "on_diff" and last is not None and last.content_hash == new_hash:
        logger.debug("Conteúdo idêntico ao último snapshot de %s — nada a versionar.", file_path)
        return None

    if last is not None:
        last.is_current = False

    snapshot = CodeSnapshot(
        file_path=file_path,
        content=new_content,
        content_hash=new_hash,
        size_bytes=len(new_content.encode("utf-8")),
        origin=origin,
        triggered_by=_current_triggered_by.get(),
        model_name=_current_model_name.get(),
        generation_run_id=_current_run_id.get(),
        is_current=True,
        parent_snapshot_id=last.id if last is not None else None,
        created_by_user_id=created_by_user_id,
    )
    db.session.add(snapshot)
    db.session.commit()
    logger.info(
        "Snapshot criado: %s (origin=%s, run=%s)",
        file_path, origin, _current_run_id.get(),
    )
    return snapshot


def cleanup_old_snapshots() -> int:
    """
    Aplica a política de retenção configurada em system_config:
    - versioning.retention_days (0 = nunca expira por idade)
    - versioning.retention_max_per_file (0 = ilimitado por arquivo)

    Padrão de fábrica: ambos 0 — nada é apagado automaticamente.
    Pensado para ser chamado por um job agendado futuro, não cria
    nenhum scheduler novo aqui.
    """
    retention_days = ConfigService.get("versioning.retention_days", default=0)
    retention_max = ConfigService.get("versioning.retention_max_per_file", default=0)

    removed = 0

    if retention_days and retention_days > 0:
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        old = (
            CodeSnapshot.query
            .filter(CodeSnapshot.created_at < cutoff)
            .filter(CodeSnapshot.is_current.is_(False))
            .all()
        )
        for s in old:
            db.session.delete(s)
            removed += 1

    if retention_max and retention_max > 0:
        paths = [r[0] for r in db.session.query(CodeSnapshot.file_path).distinct().all()]
        for path in paths:
            snapshots = (
                CodeSnapshot.query
                .filter_by(file_path=path)
                .order_by(CodeSnapshot.created_at.desc())
                .all()
            )
            excess = snapshots[retention_max:]
            for s in excess:
                if not s.is_current:
                    db.session.delete(s)
                    removed += 1

    if removed:
        db.session.commit()
        logger.info("Limpeza de snapshots: %d removido(s).", removed)

    return removed
