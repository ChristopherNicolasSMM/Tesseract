"""
core/odata/connection_manager.py

Gerenciador de Conexões OData V4 — portado quase 1:1 de
odata/connection_manager.py (DEVStationFlask). Sem nenhuma
dependência externa (só `urllib`/`json`/`xml` da stdlib) — o
"S2MOdataPy" mencionado no código original é só um FORMATO de JSON
reconhecido pelo parser, não uma biblioteca que precisa ser instalada.

Descoberta inteligente do $metadata, seguindo a mesma ordem de
prioridade do original:

  1. GET na URL base, extrai "@odata.context" do corpo JSON
  2. {base}/$metadata.json, /%24metadata.json, /metadata.json
  3. Variantes XML: $metadata, %24metadata, metadata (sem .json)

Sempre valida se a resposta é JSON ou XML antes de processar.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

log = logging.getLogger(__name__)

METADATA_TTL_SECONDS = 300  # 5 minutos — mesmo valor do original


class ParseError(Exception):
    """Erro interno de parse de metadata."""


class ODataConnectionManager:
    """Serviço de acesso a servidores OData V4 com descoberta de metadados."""

    def __init__(self, connection):
        self.conn = connection

    # ── Metadados (ponto de entrada público) ────────────────────────────

    def fetch_metadata(self, force_refresh: bool = False) -> dict:
        """Retorna os metadados do servidor OData, com cache de 5 minutos.

        Fase 10 (Patch 2): quando `self.conn.is_local`, pula cache e
        descoberta HTTP inteiramente — o metadata é montado ao vivo a
        partir dos models @odata_expose já carregados em memória
        (core/odata_provider/metadata.py), então cachear só
        acrescentaria a chance de servir schema desatualizado depois
        de um Model Builder mudar um model em runtime, sem nenhum
        ganho de performance real (é só um dict comprehension)."""
        if self.conn.is_local:
            from core.odata_provider.metadata import build_metadata_json
            return build_metadata_json()

        from core.db import db

        if not force_refresh and self.conn.metadata_cache and self.conn.metadata_cached_at:
            cached_at = self.conn.metadata_cached_at
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age < METADATA_TTL_SECONDS:
                return self.conn.metadata_cache

        data = self._discover_and_fetch_metadata()

        self.conn.metadata_cache = data
        self.conn.metadata_cached_at = datetime.now(timezone.utc)
        db.session.commit()

        return data

    # ── Cadeia de descoberta ─────────────────────────────────────────────

    def _discover_and_fetch_metadata(self) -> dict:
        base = self.conn.base_url.rstrip("/")
        # Bugfix (BACKLOG.md, "Bugs de OData"): se a URL cadastrada já
        # É o próprio $metadata (usuário colou a URL de metadata em vez
        # da raiz do serviço), não concatena mais nada em cima dela —
        # tenta ela mesma primeiro, e usa a raiz "descascada" como base
        # para o restante da cadeia (fallback, caso a tentativa direta
        # falhe por qualquer motivo).
        root = _strip_metadata_suffix(base)
        tried: set = set()
        candidates = []
        errors = []

        if root != base:
            candidates.append((base, "auto"))

        ctx_base = self._extract_context_base(root)
        if ctx_base:
            log.info("@odata.context encontrado -> base de metadata: %s", ctx_base)
            candidates.append((ctx_base + ".json", "json"))
            candidates.append((ctx_base, "auto"))

        for path in ("/$metadata.json", "/%24metadata.json", "/metadata.json"):
            candidates.append((root + path, "json"))

        for path in ("/$metadata", "/%24metadata", "/metadata"):
            candidates.append((root + path, "xml"))

        for url, fmt_hint in candidates:
            clean = url.split("#")[0]
            if clean in tried:
                continue
            tried.add(clean)
            log.debug("Testando metadata URL: %s [%s]", clean, fmt_hint)

            try:
                raw = self._get(clean, accept=_accept_header(fmt_hint))
                parsed = self._parse_response(raw, clean)
                log.info("Metadata obtido com sucesso: %s", clean)
                return parsed
            except urllib.error.HTTPError as e:
                errors.append(f"HTTP {e.code}: {clean}")
            except urllib.error.URLError as e:
                errors.append(f"URLError ({e.reason}): {clean}")
            except ParseError as e:
                errors.append(f"ParseError ({e}): {clean}")
            except Exception as e:
                errors.append(f"{type(e).__name__} ({e}): {clean}")

        raise RuntimeError(
            "Não foi possível encontrar o $metadata do servidor OData.\n"
            "URLs tentadas:\n" + "\n".join(f"  - {e}" for e in errors) + "\n\n"
            "Verifique se o servidor expõe /$metadata.json (JSON) ou /$metadata (XML)."
        )

    def _extract_context_base(self, base_url: str) -> str | None:
        try:
            raw = self._get(base_url, accept="application/json")
            body = json.loads(raw)
            ctx = body.get("@odata.context") or body.get("odata.context") or ""
            if not ctx:
                return None
            return ctx.split("#")[0]
        except Exception as exc:
            log.debug("_extract_context_base falhou (%s): %s", base_url, exc)
            return None

    # ── Parser de resposta ───────────────────────────────────────────────

    def _parse_response(self, raw: str, url: str) -> dict:
        text = (raw if isinstance(raw, str) else raw.decode("utf-8")).strip()
        if not text:
            raise ParseError("Resposta vazia")

        if text.startswith("<") or "<?xml" in text[:200]:
            return self._parse_xml(text, url)

        try:
            data = json.loads(text)
            return self._normalize_json(data, url)
        except json.JSONDecodeError as exc:
            raise ParseError(f"Nem JSON nem XML reconhecido: {exc}") from exc

    def _normalize_json(self, data, url: str) -> dict:
        """
        Suporta: formato {"entities": [...]}, EDMX JSON (EntityType/
        Property), ou lista direta de entidades.
        """
        if isinstance(data, dict) and "entities" in data:
            data["_source_format"] = "json"
            return data

        if isinstance(data, dict) and ("EntityType" in data or "EntityContainer" in data):
            ets = data.get("EntityType", [])
            if isinstance(ets, dict):
                ets = [ets]

            # Mesma correção da seção XML (ver _parse_xml) — aqui pro
            # formato EDMX expresso em JSON.
            entity_set_by_type = _extract_entity_set_map_json(data.get("EntityContainer"))

            entities = []
            for et in ets:
                type_name = et.get("Name") or et.get("name", "Unknown")
                props = et.get("Property") or et.get("properties", [])
                if isinstance(props, dict):
                    props = [props]
                fields = [_edm_prop_to_field(p) for p in props]
                route_name = entity_set_by_type.get(type_name, type_name)
                entities.append({
                    "name": route_name,
                    "label": type_name,
                    "entity_type_name": type_name,
                    "fields": fields,
                    "ui": {},
                })
            return {"entities": entities, "_source_format": "json"}

        if isinstance(data, list):
            return {"entities": data, "_source_format": "json"}

        log.warning("Formato JSON de metadata não reconhecido em %s", url)
        return {"entities": [], "_source_format": "json"}

    def _parse_xml(self, xml_text: str, url: str) -> dict:
        try:
            root = ET.fromstring(xml_text)
        except Exception as exc:
            raise ParseError(f"XML inválido: {exc}") from exc

        # Bugfix (BACKLOG.md, "Bugs de OData"): a URL navegável de uma
        # coleção é o nome do EntitySet (normalmente plural, ex.
        # "Products"), declarado no EntityContainer — não o nome do
        # EntityType (normalmente singular, ex. "Product"). Sem esse
        # mapa, o browse tentava a rota errada e recebia 404.
        entity_set_by_type = _extract_entity_set_map_xml(root)

        entities = []
        for el in root.iter():
            local = el.tag.split("}")[-1]
            if local != "EntityType":
                continue
            type_name = el.get("Name", "Unknown")
            fields = []
            for child in el:
                child_local = child.tag.split("}")[-1]
                if child_local == "Property":
                    fields.append(_edm_prop_to_field(child.attrib))
            route_name = entity_set_by_type.get(type_name, type_name)
            entities.append({
                "name": route_name,
                "label": type_name,
                "entity_type_name": type_name,
                "fields": fields,
                "ui": {},
            })

        if not entities:
            log.warning("XML EDMX sem EntityType em %s", url)

        return {"entities": entities, "_source_format": "xml"}

    # ── Dados ────────────────────────────────────────────────────────────

    def list_entities(self) -> list[dict]:
        meta = self.fetch_metadata()
        overrides = self.conn.entity_route_overrides or {}
        result = []
        for e in meta.get("entities", []):
            declared_name = e.get("name", "")
            result.append({
                # Bugfix (BACKLOG.md, "Bugs de OData"): nome usado pra
                # montar a URL de browse/query — já com override manual
                # aplicado, se existir (skill 06 do formato customizado
                # sem EntitySet).
                "name": overrides.get(declared_name, declared_name),
                "declared_name": declared_name,
                "label": e.get("label", declared_name),
                "description": e.get("description", ""),
                "fields": e.get("fields", []),
                "ui": e.get("ui", {}),
            })
        return result

    def get_entity(self, entity_name: str) -> dict | None:
        for ent in self.list_entities():
            if ent["name"] == entity_name:
                return ent
        return None

    def query(self, entity: str, params: dict | None = None) -> dict:
        """GET na coleção com parâmetros OData ($filter, $orderby, $top, etc.).

        Fase 10 (Patch 2): quando `self.conn.is_local`, chama
        core/odata_provider/service.py direto, em processo — sem HTTP,
        sem a heurística de pluralização abaixo (ela só existe porque
        servidores externos podem nomear a rota diferente do
        EntityType; aqui o provedor local controla os dois lados do
        nome, então nunca diverge).

        Bugfix (BACKLOG.md, "Bugs de OData"): se `entity` der 404 e o
        formato de metadata não tinha como declarar o nome real da
        rota (sem EntitySet), tenta uma pluralização simples como
        último recurso e, se funcionar, persiste como override — não
        tenta adivinhar de novo nas próximas chamadas.
        """
        if self.conn.is_local:
            return self._query_local(entity, params)

        try:
            return self._query_raw(entity, params)
        except urllib.error.HTTPError as original_error:
            if original_error.code != 404:
                raise
            guess = _pluralize_guess(entity)
            if guess == entity:
                raise
            try:
                result = self._query_raw(guess, params)
            except Exception:
                raise original_error
            self._persist_route_override(entity, guess)
            return result

    def _query_local(self, entity: str, params: dict | None) -> dict:
        from flask_login import current_user
        from core.odata_provider.service import query_local, EntityNotExposedError, PermissionDeniedError

        try:
            return query_local(entity, params, user=current_user)
        except EntityNotExposedError as exc:
            raise RuntimeError(f"Entidade '{exc}' não exposta pelo provedor local (@odata_expose ausente).") from exc
        except PermissionDeniedError as exc:
            raise RuntimeError(f"Permissão necessária para acessar '{entity}': {exc}.") from exc

    def _query_raw(self, entity: str, params: dict | None) -> dict:
        qs = ""
        if params:
            parts = [f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items() if v]
            if parts:
                qs = "?" + "&".join(parts)
        raw = self._get(self._build_url(f"{entity}{qs}"))
        return json.loads(raw) if isinstance(raw, (str, bytes)) else raw

    def set_route_override(self, declared_name: str, route_name: str) -> None:
        """Confirma/corrige manualmente o nome de rota de uma entidade
        (tela 'Ver entidades') — mesmo mecanismo usado pelo fallback
        automático de `query()`, só que disparado pelo usuário."""
        self._persist_route_override(declared_name, route_name)

    def _persist_route_override(self, declared_name: str, resolved_name: str) -> None:
        from core.db import db

        overrides = dict(self.conn.entity_route_overrides or {})
        overrides[declared_name] = resolved_name
        self.conn.entity_route_overrides = overrides
        db.session.commit()

    def patch(self, entity: str, key: str, data: dict) -> dict:
        if self.conn.is_local:
            from flask_login import current_user
            from core.odata_provider.service import patch_local, EntityNotExposedError, PermissionDeniedError

            try:
                return patch_local(entity, key, data, user=current_user)
            except EntityNotExposedError as exc:
                raise RuntimeError(f"Entidade '{exc}' não exposta pelo provedor local (@odata_expose ausente).") from exc
            except PermissionDeniedError as exc:
                raise RuntimeError(f"Permissão necessária para editar '{entity}': {exc}.") from exc

        url = self._build_url(f"{entity}({key})")
        raw = self._request("PATCH", url, data)
        return json.loads(raw) if isinstance(raw, (str, bytes)) else {}

    # ── Teste de conexão ─────────────────────────────────────────────────

    def test_connection(self) -> dict:
        try:
            meta = self.fetch_metadata(force_refresh=True)
            n = len(meta.get("entities", []))
            fmt = meta.get("_source_format", "json")
            return {
                "ok": True,
                "entities_count": n,
                "source_format": fmt,
                "message": f"{n} entidade(s) encontrada(s) (formato: {fmt})",
            }
        except RuntimeError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            log.warning("test_connection falhou: %s", exc)
            return {"ok": False, "error": str(exc)}

    # ── HTTP helpers ─────────────────────────────────────────────────────

    def _build_url(self, path: str) -> str:
        return self.conn.base_url.rstrip("/") + "/" + path

    def _auth_headers(self) -> dict:
        h = {}
        if self.conn.auth_type == "bearer" and self.conn.auth_value:
            h["Authorization"] = f"Bearer {self.conn.auth_value}"
        elif self.conn.auth_type == "basic" and self.conn.auth_value:
            import base64
            creds = base64.b64encode(self.conn.auth_value.encode()).decode()
            h["Authorization"] = f"Basic {creds}"
        return h

    def _get(self, url: str, accept: str = "application/json") -> str:
        headers = {"Accept": accept, **self._auth_headers()}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")

    def _request(self, method: str, url: str, body: dict) -> str:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **self._auth_headers(),
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")


def _extract_entity_set_map_xml(root: ET.Element) -> dict:
    """Varre o XML procurando <EntitySet Name="..." EntityType="Ns.Tipo"/>
    (dentro de EntityContainer) e devolve {NomeCurtoDoTipo: NomeDoSet}."""
    mapping = {}
    for el in root.iter():
        if el.tag.split("}")[-1] != "EntitySet":
            continue
        set_name = el.get("Name")
        type_ref = el.get("EntityType", "")
        type_short = type_ref.rsplit(".", 1)[-1]
        if set_name and type_short:
            mapping[type_short] = set_name
    return mapping


def _extract_entity_set_map_json(container) -> dict:
    """Mesma ideia de `_extract_entity_set_map_xml`, para o EntityContainer
    quando o metadata vem em JSON (em vez de XML)."""
    mapping = {}
    if not isinstance(container, dict):
        return mapping
    sets = container.get("EntitySet", [])
    if isinstance(sets, dict):
        sets = [sets]
    for s in sets:
        set_name = s.get("Name") or s.get("name")
        type_ref = s.get("EntityType") or s.get("entityType") or ""
        type_short = type_ref.rsplit(".", 1)[-1]
        if set_name and type_short:
            mapping[type_short] = set_name
    return mapping


def _pluralize_guess(name: str) -> str:
    """Heurística simples de pluralização em inglês — só usada como
    'melhor esforço' de fallback (ver query()); nunca a única fonte de
    verdade. Nomes que a heurística errar podem ser corrigidos à mão
    na tela 'Ver entidades' (entity_route_overrides)."""
    if not name:
        return name
    lower = name.lower()
    if lower.endswith("y") and not lower.endswith(("ay", "ey", "iy", "oy", "uy")):
        return name[:-1] + "ies"
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return name + "es"
    return name + "s"


_METADATA_URL_SUFFIXES = (
    "/$metadata.json", "/%24metadata.json", "/metadata.json",
    "/$metadata", "/%24metadata", "/metadata",
)


def _strip_metadata_suffix(url: str) -> str:
    """Se `url` já termina apontando pro $metadata (em qualquer uma das
    variantes reconhecidas), devolve a raiz sem esse sufixo. Caso
    contrário, devolve `url` sem alteração — nunca esvazia a URL."""
    lowered = url.lower()
    for suffix in _METADATA_URL_SUFFIXES:
        if lowered.endswith(suffix.lower()):
            stripped = url[: -len(suffix)]
            return stripped or url
    return url


def _accept_header(fmt_hint: str) -> str:
    if fmt_hint == "xml":
        return "application/xml,application/atom+xml;q=0.9,*/*;q=0.8"
    if fmt_hint == "json":
        return "application/json"
    return "application/json,application/xml;q=0.8,*/*;q=0.5"


def _edm_prop_to_field(prop: dict) -> dict:
    name = prop.get("Name") or prop.get("name", "")
    raw_type = prop.get("Type") or prop.get("type", "Edm.String")
    nullable = str(prop.get("Nullable", "true")).lower()
    maxlen = prop.get("MaxLength")

    edm_map = {
        "Edm.String": "TEXT", "Edm.Int16": "NUMBER", "Edm.Int32": "NUMBER",
        "Edm.Int64": "NUMBER", "Edm.Decimal": "NUMBER", "Edm.Double": "NUMBER",
        "Edm.Single": "NUMBER", "Edm.Boolean": "BOOLEAN", "Edm.Date": "DATE",
        "Edm.DateTime": "DATE", "Edm.DateTimeOffset": "DATE",
        "Edm.Guid": "TEXT", "Edm.Binary": "TEXT",
    }
    dsb_type = edm_map.get(raw_type, "TEXT")

    return {
        "name": name,
        "label": name,
        "type": dsb_type,
        "required": nullable == "false",
        "max_length": int(maxlen) if maxlen and str(maxlen).isdigit() else None,
    }
