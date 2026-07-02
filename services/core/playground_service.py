"""
services/core/playground_service.py

API/SQL Playground (skill 06, Patch C). Duas responsabilidades bem
separadas:
- HTTP: dispara requisição real via `requests`, guarda resposta.
- SQL: só SELECT, validado por `sqlparse` ANTES de tocar no banco
  (skill 06 §6) — nunca depende só da permissão RBAC
  (`playground_requests.execute`) para barrar escrita; a validação de
  parser roda sempre, independente de quem está logado.

Bridge com o Model Builder (skill 06 §5): infere campos a partir de um
JSON de resposta e pré-preenche um ModelDefinition novo.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

import requests
import sqlparse
from flask import current_app

from core.db import db
from model.core.playground_request import PlaygroundRequest, PlaygroundRequestKind
from model.core.model_field_definition import ModelFieldType
from services.core import model_builder_service as model_builder_svc

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT_SECONDS = 15
_SQL_ROW_LIMIT = 200

_FORBIDDEN_SQL_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|"
    r"ATTACH|DETACH|PRAGMA|REPLACE|VACUUM|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)


class PlaygroundError(ValueError):
    pass


# ── HTTP ──────────────────────────────────────────────────────────────────

def execute_http_request(*, name: Optional[str], method: str, url: str,
                          headers: Optional[dict] = None, body: Optional[dict] = None,
                          created_by_user_id: Optional[int] = None) -> PlaygroundRequest:
    method = (method or "GET").upper()
    if not url:
        raise PlaygroundError("URL é obrigatória.")

    record = PlaygroundRequest(
        kind=PlaygroundRequestKind.HTTP,
        name=name,
        http_method=method,
        url=url,
        headers_json=headers or {},
        body_json=body or {},
        created_by_user_id=created_by_user_id,
    )

    try:
        response = requests.request(
            method, url, headers=headers or {}, json=body or None,
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        record.last_status_code = response.status_code
        try:
            record.last_response_json = response.json()
        except ValueError:
            # Resposta não é JSON — guarda como texto dentro de um envelope,
            # pra não quebrar a coluna JSON nem perder a informação.
            record.last_response_json = {"_raw_text": response.text[:5000]}
        record.last_error = None
    except requests.RequestException as exc:
        record.last_status_code = None
        record.last_response_json = None
        record.last_error = str(exc)
        logger.warning("Playground HTTP request falhou: %s", exc)

    db.session.add(record)
    db.session.commit()
    return record


# ── SQL (somente leitura) ────────────────────────────────────────────────

def _validate_select_only(sql_text: str) -> str:
    statements = [s for s in sqlparse.split(sql_text) if s.strip()]
    if len(statements) != 1:
        raise PlaygroundError(
            "Só uma instrução SQL por vez, e só SELECT (skill 06 §6)."
        )
    stmt = statements[0]

    if _FORBIDDEN_SQL_KEYWORDS.search(stmt):
        raise PlaygroundError("Só SELECT é permitido no SQL Playground (skill 06 §6).")

    parsed = sqlparse.parse(stmt)[0]
    stmt_type = parsed.get_type()
    if stmt_type != "SELECT" and not stmt.strip().upper().startswith("WITH"):
        raise PlaygroundError(
            f"Só SELECT é permitido no SQL Playground — instrução detectada: {stmt_type}."
        )
    return stmt


def execute_sql_select(*, name: Optional[str], sql_text: str,
                        created_by_user_id: Optional[int] = None) -> PlaygroundRequest:
    """
    Sempre valida antes de tocar no banco — independe de qualquer flag
    de system_config (skill 06 §6: `playground.sql_write_enabled` é
    reservada, sem uso ativo nesta versão; SELECT-only é reforçado
    aqui no código, não por configuração).
    """
    from sqlalchemy import text

    record = PlaygroundRequest(
        kind=PlaygroundRequestKind.SQL,
        name=name,
        sql_text=sql_text,
        created_by_user_id=created_by_user_id,
    )

    try:
        clean_stmt = _validate_select_only(sql_text)
        result = db.session.execute(text(clean_stmt))
        columns = list(result.keys())
        rows = result.fetchmany(_SQL_ROW_LIMIT)
        record.last_response_json = {
            "columns": columns,
            "rows": [[_json_safe(v) for v in row] for row in rows],
            "row_count": len(rows),
            "truncated": len(rows) == _SQL_ROW_LIMIT,
        }
        record.last_status_code = 200
        record.last_error = None
    except PlaygroundError as exc:
        db.session.rollback()
        record.last_error = str(exc)
        record.last_response_json = None
    except Exception as exc:  # noqa: BLE001 — erro de SQL real precisa chegar ao usuário
        db.session.rollback()
        record.last_error = str(exc)
        record.last_response_json = None
        logger.warning("Playground SQL falhou: %s", exc)

    db.session.add(record)
    db.session.commit()

    if record.last_error:
        # Ainda assim persiste o histórico (record já commitado acima) — só
        # sinaliza pro controller mostrar o erro.
        raise PlaygroundError(record.last_error)
    return record


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


# ── Bridge: resposta -> campos do Model Builder ─────────────────────────────

_TYPE_MAP = {
    bool: ModelFieldType.BOOLEAN,
    int: ModelFieldType.INTEGER,
    float: ModelFieldType.FLOAT,
    str: ModelFieldType.STRING,
}

_ISO_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?")


def _infer_field_type(value: Any) -> str:
    if isinstance(value, bool):
        return ModelFieldType.BOOLEAN
    if isinstance(value, int):
        return ModelFieldType.INTEGER
    if isinstance(value, float):
        return ModelFieldType.FLOAT
    if isinstance(value, str) and _ISO_DATETIME_RE.match(value):
        return ModelFieldType.DATETIME if "T" in value or ":" in value else ModelFieldType.DATE
    return ModelFieldType.STRING


def infer_fields_from_json(response_json: Any) -> list[dict]:
    """
    Skill 06 §5: infere field_name/field_type/nullable a partir de um
    JSON de resposta (objeto único, ou primeiro item se for lista).
    `nullable` considera presença/ausência da chave entre amostras
    quando a resposta é uma lista.
    """
    if isinstance(response_json, list):
        sample = response_json[:20]
        if not sample:
            return []
        keys = set()
        for item in sample:
            if isinstance(item, dict):
                keys.update(item.keys())
        fields = []
        for key in keys:
            present_in_all = all(isinstance(i, dict) and key in i for i in sample)
            first_value = next((i[key] for i in sample if isinstance(i, dict) and key in i and i[key] is not None), None)
            fields.append({
                "field_name": key,
                "field_type": _infer_field_type(first_value) if first_value is not None else ModelFieldType.STRING,
                "nullable": not present_in_all,
                "label_text": key.replace("_", " ").title(),
            })
        return fields

    if isinstance(response_json, dict):
        return [
            {
                "field_name": key,
                "field_type": _infer_field_type(value) if value is not None else ModelFieldType.STRING,
                "nullable": value is None,
                "label_text": key.replace("_", " ").title(),
            }
            for key, value in response_json.items()
        ]

    return []


def create_model_definition_from_playground(
    playground_request_id: int, *, target_addon_name: str, target_feature_name: Optional[str],
    model_name: str, table_short_name: str, created_by_user_id: Optional[int],
    is_new_addon: bool = False, is_new_feature: bool = False, manifest_draft: Optional[dict] = None,
):
    """
    Botão "Usar resposta como base de campos" (skill 06 §5) — nunca
    gera o Model direto; sempre cria um rascunho revisável no Model
    Builder, com os campos já pré-preenchidos a partir da inferência.
    """
    record = PlaygroundRequest.query.get(playground_request_id)
    if not record or not record.last_response_json:
        raise PlaygroundError("Esta requisição não tem resposta salva pra usar como base.")

    inferred = infer_fields_from_json(record.last_response_json)
    if not inferred:
        raise PlaygroundError("Não foi possível inferir nenhum campo a partir desta resposta.")

    definition = model_builder_svc.create_draft(
        target_addon_name=target_addon_name,
        target_feature_name=target_feature_name,
        model_name=model_name,
        table_short_name=table_short_name,
        created_by_user_id=created_by_user_id,
        is_new_addon=is_new_addon,
        is_new_feature=is_new_feature,
        manifest_draft=manifest_draft,
    )
    for field in inferred:
        model_builder_svc.add_field(
            definition,
            field_name=field["field_name"],
            field_type=field["field_type"],
            label_text=field["label_text"],
            nullable=field["nullable"],
        )
    return definition
