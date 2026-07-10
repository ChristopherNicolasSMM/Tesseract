"""
services/core/playground_service.py

API/SQL Playground (skill 06, Patch C + adenda "Playground v2", §8).
Duas responsabilidades bem separadas:
- HTTP: dispara requisição real via `requests`, guarda resposta.
- SQL: só SELECT, validado por `sqlparse` ANTES de tocar no banco
  (skill 06 §6) — nunca depende só da permissão RBAC
  (`playground_requests.execute`) para barrar escrita; a validação de
  parser roda sempre, independente de quem está logado.

Bridge com o Model Builder (skill 06 §5): infere campos a partir de um
JSON de resposta e pré-preenche um ModelDefinition novo.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

import requests
import sqlparse
from flask import current_app

from core.db import db
from model.core.playground_request import PlaygroundRequest, PlaygroundRequestKind, PlaygroundAuthType
from model.core.playground_folder import PlaygroundFolder
from model.core.playground_cookie_jar import PlaygroundCookieJar
from model.core.model_field_definition import ModelFieldType
from services.core import model_builder_service as model_builder_svc
from model.core.model_definition import ModelDefinition, ModelDefinitionRelationType

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


# ── Playground v2 (skill 06 §8) — Auth / Params / Cookie Jar ────────────────

def _auth_headers_for(auth_type: Optional[str], auth_config: Optional[dict]) -> dict:
    """Monta o header derivado de auth_type/auth_config (skill 06 §8.1).
    Nunca substitui headers_json — é combinado com ele."""
    auth_config = auth_config or {}
    if auth_type == PlaygroundAuthType.BEARER and auth_config.get("token"):
        return {"Authorization": f"Bearer {auth_config['token']}"}
    if auth_type == PlaygroundAuthType.BASIC and (auth_config.get("username") or auth_config.get("password")):
        creds = f"{auth_config.get('username', '')}:{auth_config.get('password', '')}"
        encoded = base64.b64encode(creds.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    if auth_type == PlaygroundAuthType.API_KEY and auth_config.get("header_name"):
        return {auth_config["header_name"]: auth_config.get("value", "")}
    return {}


def _build_query_params(params_json: Optional[list]) -> dict:
    """`params_json`: [{"key": "...", "value": "...", "enabled": true}, ...]."""
    if not params_json:
        return {}
    return {
        p["key"]: p.get("value", "")
        for p in params_json
        if p.get("enabled", True) and p.get("key")
    }


def _load_cookie_jar(user_id: Optional[int]) -> dict:
    if not user_id:
        return {}
    jar = PlaygroundCookieJar.query.filter_by(user_id=user_id).first()
    return (jar.cookies_json or {}) if jar else {}


def _save_cookie_jar(user_id: Optional[int], session: "requests.Session") -> None:
    if not user_id:
        return
    cookies_dict = session.cookies.get_dict()
    if not cookies_dict:
        return
    jar = PlaygroundCookieJar.query.filter_by(user_id=user_id).first()
    if not jar:
        jar = PlaygroundCookieJar(user_id=user_id, cookies_json=cookies_dict)
        db.session.add(jar)
    else:
        jar.cookies_json = cookies_dict
    db.session.commit()


# ── HTTP ──────────────────────────────────────────────────────────────────

def execute_http_request(*, name: Optional[str], method: str, url: str,
                          headers: Optional[dict] = None, body: Optional[dict] = None,
                          params: Optional[list] = None, auth_type: Optional[str] = None,
                          auth_config: Optional[dict] = None, folder_id: Optional[int] = None,
                          created_by_user_id: Optional[int] = None) -> PlaygroundRequest:
    """Skill 06 §8.1 — fluxo v2: monta URL final com `params` (query
    string estruturada), combina `headers` livre com o header derivado
    de `auth_type`/`auth_config`, executa numa `requests.Session()`
    pré-carregada com o cookie jar do usuário, e persiste a sessão de
    volta no jar ao final."""
    method = (method or "GET").upper()
    if not url:
        raise PlaygroundError("URL é obrigatória.")
    auth_type = auth_type or PlaygroundAuthType.NONE

    record = PlaygroundRequest(
        kind=PlaygroundRequestKind.HTTP,
        name=name,
        http_method=method,
        url=url,
        headers_json=headers or {},
        body_json=body or {},
        params_json=params or [],
        auth_type=auth_type,
        auth_config=auth_config or {},
        folder_id=folder_id,
        created_by_user_id=created_by_user_id,
    )

    final_headers = dict(headers or {})
    final_headers.update(_auth_headers_for(auth_type, auth_config))
    query_params = _build_query_params(params)

    session = requests.Session()
    session.cookies.update(_load_cookie_jar(created_by_user_id))

    try:
        response = session.request(
            method, url, headers=final_headers, params=query_params or None,
            json=body or None, timeout=_HTTP_TIMEOUT_SECONDS,
        )
        record.last_status_code = response.status_code
        try:
            record.last_response_json = response.json()
        except ValueError:
            # Resposta não é JSON — guarda como texto dentro de um envelope,
            # pra não quebrar a coluna JSON nem perder a informação.
            record.last_response_json = {"_raw_text": response.text[:5000]}
        record.last_error = None
        _save_cookie_jar(created_by_user_id, session)
    except requests.RequestException as exc:
        record.last_status_code = None
        record.last_response_json = None
        record.last_error = str(exc)
        logger.warning("Playground HTTP request falhou: %s", exc)

    db.session.add(record)
    db.session.commit()
    return record


# ── Pastas (skill 06 §8.2) ───────────────────────────────────────────────

def create_folder(*, name: str, parent_id: Optional[int] = None,
                   created_by_user_id: Optional[int] = None) -> PlaygroundFolder:
    if not name:
        raise PlaygroundError("Nome da pasta é obrigatório.")
    folder = PlaygroundFolder(name=name, parent_id=parent_id or None, created_by_user_id=created_by_user_id)
    db.session.add(folder)
    db.session.commit()
    return folder


def delete_folder(folder_id: int) -> None:
    """Bloqueado se a pasta tiver filhos (sub-pasta ou requisição) —
    sem cascade automático (skill 06 §8.2)."""
    folder = PlaygroundFolder.query.get(folder_id)
    if not folder:
        raise PlaygroundError("Pasta não encontrada.")
    has_subfolder = PlaygroundFolder.query.filter_by(parent_id=folder_id).first() is not None
    has_request = PlaygroundRequest.query.filter_by(folder_id=folder_id).first() is not None
    if has_subfolder or has_request:
        raise PlaygroundError("Pasta não está vazia — mova ou apague o conteúdo antes de remover.")
    db.session.delete(folder)
    db.session.commit()


def list_folder_tree() -> list[dict]:
    """Lista achatada em ordem de árvore (pai antes dos filhos), com
    `depth` pra indentação na UI."""
    folders = PlaygroundFolder.query.order_by(PlaygroundFolder.name).all()
    by_parent: dict = {}
    for f in folders:
        by_parent.setdefault(f.parent_id, []).append(f)

    result: list[dict] = []

    def _walk(parent_id, depth):
        for f in by_parent.get(parent_id, []):
            result.append({"id": f.id, "name": f.name, "parent_id": f.parent_id, "depth": depth})
            _walk(f.id, depth + 1)

    _walk(None, 0)
    return result


def move_request_to_folder(request_id: int, folder_id: Optional[int]) -> PlaygroundRequest:
    record = PlaygroundRequest.query.get(request_id)
    if not record:
        raise PlaygroundError("Requisição não encontrada.")
    record.folder_id = folder_id or None
    db.session.commit()
    return record


# ── Arquivar / Apagar (skill 06 §8.3 — ações separadas) ─────────────────────

def set_archived(request_id: int, archived: bool) -> PlaygroundRequest:
    record = PlaygroundRequest.query.get(request_id)
    if not record:
        raise PlaygroundError("Requisição não encontrada.")
    record.is_archived = archived
    db.session.commit()
    return record


def delete_request(request_id: int) -> None:
    """DELETE físico — este model não segue soft-delete (skill 00,
    Adendo Fase 7a); 'apagar' é sempre definitivo, diferente de
    'arquivar'."""
    record = PlaygroundRequest.query.get(request_id)
    if not record:
        raise PlaygroundError("Requisição não encontrada.")
    db.session.delete(record)
    db.session.commit()


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
    if isinstance(value, dict):
        return ModelFieldType.TABLE  # objeto aninhado -> tabela filha 1:1 (skill 06, decisao em conversa)
    if isinstance(value, list):
        sample = next((v for v in value if v is not None), None)
        if isinstance(sample, dict):
            return ModelFieldType.TABLE  # array de objetos -> tabela filha 1:N
        return ModelFieldType.JSON  # array de valores simples (sem objeto) -> continua json, sem tabela
    if isinstance(value, int):
        return ModelFieldType.INTEGER
    if isinstance(value, float):
        return ModelFieldType.FLOAT
    if isinstance(value, str) and _ISO_DATETIME_RE.match(value):
        return ModelFieldType.DATETIME if "T" in value or ":" in value else ModelFieldType.DATE
    return ModelFieldType.STRING


def _infer_json_schema(value: Any, *, depth: int = 0) -> Optional[list]:
    """Infere os sub-campos de um array de valores simples pra virar
    `json_schema` (metadado de documentacao, skill 06 -- so usado
    quando o campo continua `json`; objeto/array-de-objeto agora vira
    tabela filha de verdade, ver `_infer_table_relation()`). Recursivo
    ate 2 niveis, evita arvore infinita em JSON muito aninhado."""
    if depth > 1:
        return None

    if isinstance(value, list):
        sample = next((v for v in value if v is not None), None)
        if isinstance(sample, dict):
            return [
                {
                    "name": key,
                    "type": _infer_field_type(val),
                    "children": _infer_json_schema(val, depth=depth + 1) if isinstance(val, (dict, list)) else None,
                }
                for key, val in sample.items()
            ]
        return None

    if isinstance(value, dict):
        return [
            {
                "name": key,
                "type": _infer_field_type(val),
                "children": _infer_json_schema(val, depth=depth + 1) if isinstance(val, (dict, list)) else None,
            }
            for key, val in value.items()
        ]

    return None


def _infer_table_relation(value: Any) -> Optional[dict]:
    """Skill 06 -- Model Builder, tabela filha de verdade. Objeto
    aninhado (dict) vira relacao 1:1; array de objetos vira relacao
    1:N. Os campos do filho sao inferidos 1 nivel (cap decidido em
    conversa/BACKLOG.md -- dentro do filho, um dict/list aninhado de
    novo cai de volta pra `json` de documentacao, nao vira neto)."""
    if isinstance(value, dict):
        return {
            "relation_type": ModelDefinitionRelationType.ONE_TO_ONE,
            "child_fields": _infer_fields_no_relation(value),
        }
    if isinstance(value, list):
        sample = next((v for v in value if v is not None), None)
        if isinstance(sample, dict):
            return {
                "relation_type": ModelDefinitionRelationType.ONE_TO_MANY,
                "child_fields": _infer_fields_no_relation(sample),
            }
    return None


def _infer_fields_no_relation(obj: dict) -> list[dict]:
    """Mesma logica de `infer_fields_from_json` pra um dict unico, mas
    sem permitir relacao de tabela de novo (cap de 1 nivel) -- um
    dict/list aninhado aqui dentro vira `json` de documentacao."""
    result = []
    for key, value in obj.items():
        field_type = _infer_field_type(value) if value is not None else ModelFieldType.STRING
        if field_type == ModelFieldType.TABLE:
            field_type = ModelFieldType.JSON  # cap de 1 nivel -- nao cria neto automaticamente
        result.append({
            "field_name": key,
            "field_type": field_type,
            "nullable": value is None,
            "label_text": key.replace("_", " ").title(),
            "json_schema": _infer_json_schema(value) if field_type == ModelFieldType.JSON else None,
        })
    return result


def infer_fields_from_json(response_json: Any) -> list[dict]:
    """
    Skill 06 SS5: infere field_name/field_type/nullable a partir de um
    JSON de resposta (objeto unico, ou primeiro item se for lista).
    `nullable` considera presenca/ausencia da chave entre amostras
    quando a resposta e uma lista. Campo cujo valor e objeto ou array
    de objetos vira `field_type=table` (relacao de verdade, com
    `relation` preenchido) -- antes virava `json` e a estrutura ficava
    so documentada, sem gerar tabela/CRUD de fato (achado real, ver
    BACKLOG.md). Array de valores simples (sem objeto) continua `json`.
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
            field_type = _infer_field_type(first_value) if first_value is not None else ModelFieldType.STRING
            fields.append({
                "field_name": key,
                "field_type": field_type,
                "nullable": not present_in_all,
                "label_text": key.replace("_", " ").title(),
                "json_schema": _infer_json_schema(first_value) if field_type == ModelFieldType.JSON else None,
                "relation": _infer_table_relation(first_value) if field_type == ModelFieldType.TABLE else None,
            })
        return fields

    if isinstance(response_json, dict):
        result = []
        for key, value in response_json.items():
            field_type = _infer_field_type(value) if value is not None else ModelFieldType.STRING
            result.append({
                "field_name": key,
                "field_type": field_type,
                "nullable": value is None,
                "label_text": key.replace("_", " ").title(),
                "json_schema": _infer_json_schema(value) if field_type == ModelFieldType.JSON else None,
                "relation": _infer_table_relation(value) if field_type == ModelFieldType.TABLE else None,
            })
        return result

    return []




def create_model_definition_from_playground(
    playground_request_id: int, *, target_addon_name: str, target_feature_name: Optional[str],
    model_name: str, table_short_name: str, created_by_user_id: Optional[int], project_root,
    is_new_addon: bool = False, is_new_feature: bool = False, manifest_draft: Optional[dict] = None,
):
    """
    Botao "Usar resposta como base de campos" (skill 06 SS5) -- nunca
    gera o Model direto; sempre cria um rascunho revisavel no Model
    Builder, com os campos ja pre-preenchidos a partir da inferencia.
    Campos tipo `table` ja nascem com o Model filho criado (skill 06,
    tabela filha de verdade) e os campos dele ja inferidos junto.
    """
    record = PlaygroundRequest.query.get(playground_request_id)
    if not record or not record.last_response_json:
        raise PlaygroundError("Esta requisicao nao tem resposta salva pra usar como base.")

    inferred = infer_fields_from_json(record.last_response_json)
    if not inferred:
        raise PlaygroundError("Nao foi possivel inferir nenhum campo a partir desta resposta.")

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
        if field["field_type"] == model_builder_svc.ModelFieldType.TABLE:
            relation = field["relation"]
            child_field = model_builder_svc.add_table_field(
                definition,
                field_name=field["field_name"],
                label_text=field["label_text"],
                child_model_name=model_builder_svc._to_pascal_case(model_builder_svc._to_snake_case(field["field_name"])),
                child_table_short_name=model_builder_svc._to_snake_case(field["field_name"]),
                relation_type=relation["relation_type"],
                project_root=project_root,
                created_by_user_id=created_by_user_id,
            )
            child_definition = ModelDefinition.query.get(child_field.child_model_definition_id)
            for child_field_data in relation["child_fields"]:
                model_builder_svc.add_field(
                    child_definition,
                    field_name=child_field_data["field_name"],
                    field_type=child_field_data["field_type"],
                    label_text=child_field_data["label_text"],
                    nullable=child_field_data["nullable"],
                    json_schema=child_field_data.get("json_schema"),
                )
        else:
            model_builder_svc.add_field(
                definition,
                field_name=field["field_name"],
                field_type=field["field_type"],
                label_text=field["label_text"],
                nullable=field["nullable"],
                json_schema=field.get("json_schema"),
            )
    return definition
