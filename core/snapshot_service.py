"""
core/snapshot_service.py

Camada de leitura e operações sobre o histórico de versionamento
(CodeSnapshot) — portado quase 1:1 de
services/core/admin/snapshot_service.py (PyTeca), que tinha o schema
pronto pra diff/restauração desde a Fase 3, mas nenhuma API/tela
consumia isso ainda.

Função aqui é estritamente "recuperar e comparar versões" — a edição
de fato do arquivo (escrever código novo) continua sendo feita pelo
CrudGen ou manualmente, nunca por aqui.
"""
from __future__ import annotations

import difflib
import hashlib
from pathlib import Path

from core.db import db
from model.core.code_snapshot import CodeSnapshot, SnapshotOrigin


class SnapshotService:

    @classmethod
    def list_files(cls, search: str | None = None) -> list[dict]:
        """
        Lista, para cada file_path distinto, a versão atual
        (is_current=True) com metadados resumidos — popula a lista de
        "arquivos com histórico" na tela.
        """
        query = CodeSnapshot.query.filter_by(is_current=True)
        if search:
            query = query.filter(CodeSnapshot.file_path.ilike(f"%{search}%"))

        current_snapshots = query.order_by(CodeSnapshot.file_path).all()

        result = []
        for snap in current_snapshots:
            version_count = CodeSnapshot.query.filter_by(file_path=snap.file_path).count()
            result.append({
                "file_path": snap.file_path,
                "current_snapshot_id": snap.id,
                "version_count": version_count,
                "last_modified": snap.created_at.isoformat() if snap.created_at else None,
                "last_origin": snap.origin,
                "model_name": snap.model_name,
            })
        return result

    @classmethod
    def get_history(cls, file_path: str) -> list[dict]:
        """Histórico completo de um arquivo, mais recente primeiro — sem `content`."""
        snapshots = (
            CodeSnapshot.query
            .filter_by(file_path=file_path)
            .order_by(CodeSnapshot.created_at.desc())
            .all()
        )
        return [s.to_dict() for s in snapshots]

    @classmethod
    def get_content(cls, snapshot_id: int) -> dict | None:
        snap = db.session.get(CodeSnapshot, snapshot_id)
        if not snap:
            return None
        d = snap.to_dict()
        d["content"] = snap.content
        return d

    @classmethod
    def diff(cls, snapshot_id_a: int, snapshot_id_b: int) -> dict | None:
        """
        Diff unificado entre dois snapshots do MESMO arquivo. Retorna
        None se algum não existir ou forem de arquivos diferentes.
        """
        snap_a = db.session.get(CodeSnapshot, snapshot_id_a)
        snap_b = db.session.get(CodeSnapshot, snapshot_id_b)
        if not snap_a or not snap_b:
            return None
        if snap_a.file_path != snap_b.file_path:
            return None

        lines_a = snap_a.content.splitlines(keepends=True)
        lines_b = snap_b.content.splitlines(keepends=True)

        label_a = f"{snap_a.file_path} ({snap_a.created_at.strftime('%d/%m/%Y %H:%M')})"
        label_b = f"{snap_b.file_path} ({snap_b.created_at.strftime('%d/%m/%Y %H:%M')})"

        unified = "".join(difflib.unified_diff(
            lines_a, lines_b, fromfile=label_a, tofile=label_b, lineterm="\n",
        ))

        return {
            "file_path": snap_a.file_path,
            "snapshot_a": snap_a.to_dict(),
            "snapshot_b": snap_b.to_dict(),
            "identical": snap_a.content_hash == snap_b.content_hash,
            "unified_diff": unified,
        }

    @classmethod
    def restore(cls, snapshot_id: int, *, write_to_disk: bool = True,
                created_by_user_id: int | None = None) -> dict:
        """
        Restaura uma versão antiga — grava no disco (se write_to_disk)
        e cria um NOVO snapshot com origin=RESTORE, encadeado à versão
        que era corrente antes (parent_snapshot_id). Nunca silenciosa:
        a própria restauração entra no histórico.
        """
        old = db.session.get(CodeSnapshot, snapshot_id)
        if not old:
            return {"success": False, "error": "Snapshot não encontrado."}

        current = (
            CodeSnapshot.query
            .filter_by(file_path=old.file_path, is_current=True)
            .order_by(CodeSnapshot.created_at.desc())
            .first()
        )

        if current and current.id == old.id:
            return {"success": False, "error": "Esta já é a versão atual — nada para restaurar."}

        if write_to_disk:
            try:
                path = Path(old.file_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(old.content, encoding="utf-8")
            except OSError as e:
                return {"success": False, "error": f"Falha ao escrever no disco: {e}"}

        if current:
            current.is_current = False

        new_hash = hashlib.sha256(old.content.encode("utf-8")).hexdigest()
        restored = CodeSnapshot(
            file_path=old.file_path,
            content=old.content,
            content_hash=new_hash,
            size_bytes=len(old.content.encode("utf-8")),
            origin=SnapshotOrigin.RESTORE,
            triggered_by="ui:snapshot_viewer",
            model_name=old.model_name,
            is_current=True,
            parent_snapshot_id=current.id if current else old.id,
            created_by_user_id=created_by_user_id,
        )
        db.session.add(restored)
        db.session.commit()

        return {
            "success": True,
            "message": f"Versão de {old.created_at.strftime('%d/%m/%Y %H:%M')} restaurada com sucesso.",
            "snapshot": restored.to_dict(),
        }
