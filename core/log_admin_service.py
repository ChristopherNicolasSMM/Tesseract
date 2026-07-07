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

Parsing de linha (adenda desta rodada — filtro por data/hora + cor por
nível na tela): o formato de linha gravado por
`core/logging_config.py` (`%(asctime)s | %(levelname)-8s | %(name)s |
%(message)s`, datefmt `%Y-%m-%d %H:%M:%S`) é parseável via regex.
Linhas que não batem esse formato (ex.: continuação de traceback de
exceção não tratada) são anexadas à mensagem da linha anterior — nunca
viram um registro novo sem nível.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from flask import current_app

CORE_SOURCE_ID = "core"

# Ex.: "2026-07-07 15:43:00 | INFO     | core.module_manager | mensagem"
_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| "
    r"(?P<level>[A-Z]+)\s*\| (?P<logger>[^|]+?) \| (?P<message>.*)$"
)
_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _project_root() -> Path:
    return Path(current_app.root_path).parent.resolve()


def _parse_lines(raw_lines: list[str]) -> list[dict]:
    """
    Agrupa linhas cruas em registros — uma linha que não bate o
    formato padrão (ex.: linha 2+ de um traceback) é anexada à
    mensagem do registro anterior, nunca vira registro novo sem
    timestamp/nível.
    """
    registros: list[dict] = []
    for raw in raw_lines:
        linha = raw.rstrip("\n")
        m = _LINE_RE.match(linha)
        if m:
            registros.append({
                "timestamp": m.group("timestamp"),
                "timestamp_dt": datetime.strptime(m.group("timestamp"), _TIMESTAMP_FORMAT),
                "level": m.group("level"),
                "logger": m.group("logger"),
                "message": m.group("message"),
            })
        elif registros:
            registros[-1]["message"] += "\n" + linha
        else:
            # Primeira linha do arquivo já foge do formato — registro
            # sem timestamp/nível, preserva o conteúdo mesmo assim.
            registros.append({
                "timestamp": None, "timestamp_dt": None,
                "level": None, "logger": None, "message": linha,
            })
    return registros


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
    def read_content(
        cls,
        source_id: str,
        max_lines: int = 1000,
        desde: datetime | None = None,
        ate: datetime | None = None,
    ) -> dict:
        """
        Sem `desde`/`ate`: comportamento original — só as últimas
        `max_lines` linhas cruas (tail), sem parsing.

        Com `desde` e/ou `ate`: varre o arquivo INTEIRO (ignora
        `max_lines`) — um filtro pra uma janela mais antiga que as
        últimas `max_lines` linhas não pode simplesmente não achar
        nada. Devolve registros parseados (timestamp/level/logger/
        message), não linhas cruas, pra tela poder colorir por nível.
        """
        path = cls._resolve_path(source_id)
        if path is None:
            return {"error": "Fonte de log desconhecida.", "lines": [], "records": [], "truncated": False}
        if not path.exists():
            return {"error": "Arquivo ainda não foi criado.", "lines": [], "records": [], "truncated": False}

        with path.open("r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        filtro_ativo = desde is not None or ate is not None

        if not filtro_ativo:
            truncated = len(all_lines) > max_lines
            tail = all_lines[-max_lines:] if truncated else all_lines
            return {
                "error": None,
                "lines": [line.rstrip("\n") for line in tail],
                "records": _parse_lines(tail),
                "truncated": truncated,
            }

        registros = _parse_lines(all_lines)
        filtrados = [
            r for r in registros
            if r["timestamp_dt"] is not None
            and (desde is None or r["timestamp_dt"] >= desde)
            and (ate is None or r["timestamp_dt"] <= ate)
        ]
        return {
            "error": None,
            "lines": [],
            "records": filtrados,
            "truncated": False,
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
