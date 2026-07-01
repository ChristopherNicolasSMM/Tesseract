"""
core/log_admin_service.py

Camada de leitura/exclusão de arquivos de log para a tela admin de
Logs (skill 08 §6). Fonte de dados é sempre arquivo puro no disco —
nunca tabela nova (decisão fechada, skill 08 §6.1).

Só reconhece duas categorias de fonte, nunca um caminho arbitrário do
disco (skill 08, checklist §8):
- o log global do Core (<raiz do projeto>/logs/core.log);
- o log local de integração de cada Addon que declarar
  `addon.json.logging` (skill 03), descoberto em runtime via
  `current_app.module_manager.active_modules` — nunca hardcoded.

Convenção de pasta de Addon (skill 00): a pasta é sempre `addon_` +
`manifest["name"]` — usada aqui pra resolver o caminho sem precisar
que ModuleManager exponha o Path de cada Addon.
"""
from __future__ import annotations

from pathlib import Path

from flask import current_app

CORE_SOURCE_ID = "core"


def _project_root() -> Path:
    return Path(current_app.root_path).parent.resolve()


class LogAdminService:

    @classmethod
    def list_sources(cls) -> list[dict]:
        sources = [
            cls._describe(
                CORE_SOURCE_ID,
                "Log Global do Core",
                _project_root() / "logs" / "core.log",
            )
        ]

        module_manager = getattr(current_app, "module_manager", None)
        if module_manager is None:
            return sources

        for name, module in sorted(module_manager.active_modules.items()):
            manifest = getattr(module, "manifest", None) or {}
            if manifest.get("type") != "addon":
                continue

            logging_cfg = manifest.get("logging")
            if not logging_cfg or not logging_cfg.get("integration_log_enabled", True):
                continue

            log_path_relative = logging_cfg.get("integration_log_path", "logs/integration.log")
            addon_root = _project_root() / "addons" / f"addon_{name}"
            log_path = addon_root / log_path_relative

            sources.append(cls._describe(
                f"addon:{name}",
                f"Log de integração — {manifest.get('label', name)}",
                log_path,
            ))

        return sources

    @staticmethod
    def _describe(source_id: str, label: str, path: Path) -> dict:
        exists = path.exists()
        stat = path.stat() if exists else None
        return {
            "id": source_id,
            "label": label,
            "path": str(path),
            "exists": exists,
            "size_bytes": stat.st_size if stat else 0,
            "modified_at": stat.st_mtime if stat else None,
        }

    @classmethod
    def _resolve_path(cls, source_id: str) -> Path | None:
        for source in cls.list_sources():
            if source["id"] == source_id:
                return Path(source["path"])
        return None

    @classmethod
    def read_content(cls, source_id: str, max_lines: int = 1000) -> dict:
        path = cls._resolve_path(source_id)
        if path is None:
            return {"error": "Fonte de log desconhecida.", "lines": [], "truncated": False}
        if not path.exists():
            return {"error": "Arquivo ainda não foi criado.", "lines": [], "truncated": False}

        with path.open("r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        truncated = len(all_lines) > max_lines
        tail = all_lines[-max_lines:] if truncated else all_lines
        return {
            "error": None,
            "lines": [line.rstrip("\n") for line in tail],
            "truncated": truncated,
        }

    @classmethod
    def delete(cls, source_id: str) -> dict:
        path = cls._resolve_path(source_id)
        if path is None:
            return {"success": False, "error": "Fonte de log desconhecida."}
        if not path.exists():
            return {"success": False, "error": "Arquivo já não existe."}

        path.unlink()
        return {"success": True, "error": None}
