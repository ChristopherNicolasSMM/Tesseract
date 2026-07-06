"""
addons/addon_brewstation/features/feature_brew_father/services/brewfather_client.py

Cliente da API do BrewFather — stdlib apenas (urllib, base64, json).
Lê credenciais do .env via os.environ.

CORREÇÃO (bug 500): o endpoint GET /v2/recipes retorna apenas resumo
por receita — não aceita include[]=ingredients, o que causava HTTP 500.
Para obter mash steps, fermentation steps e specs completos de
ingredientes, busca-se o detalhe de cada receita via GET /v2/recipes/{id}
(chamada individual por receita, aceitável pois sync não é operação
em tempo real).
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

_BASE_URL = "https://api.brewfather.app/v2"
_DEFAULT_LIMIT = 50


class BrewFatherAPIError(Exception):
    pass


class BrewFatherDisabledError(Exception):
    pass


def _is_enabled() -> bool:
    return os.environ.get("BREWFATHER_ENABLED", "false").lower() in ("true", "1", "yes")


def _is_testing() -> bool:
    try:
        from flask import current_app
        return current_app.config.get("TESTING", False)
    except RuntimeError:
        return os.environ.get("TESSERACT_ENV", "").lower() == "testing"


def _auth_header() -> str:
    user_id = os.environ.get("BREWFATHER_USER_ID", "").strip()
    api_key = os.environ.get("BREWFATHER_API_KEY", "").strip()
    if not user_id or not api_key:
        raise BrewFatherAPIError(
            "BREWFATHER_USER_ID ou BREWFATHER_API_KEY não configurados no .env"
        )
    token = base64.b64encode(f"{user_id}:{api_key}".encode()).decode()
    return f"Basic {token}"


def _get(path: str, params: dict | None = None) -> dict | list:
    url = f"{_BASE_URL}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers={
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise BrewFatherAPIError(f"BrewFather API HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise BrewFatherAPIError(f"BrewFather API connection error: {exc.reason}") from exc


def _normalizar_ingredientes(recipe_raw: dict) -> list[dict]:
    ingredientes = []

    for malte in recipe_raw.get("fermentables", []) or []:
        ingredientes.append({
            "tipo_ingrediente": "fermentavel",
            "name": malte.get("name", ""),
            "amount": malte.get("amount", 0),
            "unit": "kg",
            "time": None,
            "use": "mostura",
            "uso_detalhado": None,
            "cor_ebc": malte.get("color"),
            "rendimento": malte.get("yield"),
            "alpha_acidos": None,
            "atenuacao": None,
        })

    for lupulo in recipe_raw.get("hops", []) or []:
        uso_bf = (lupulo.get("use") or "").lower()
        etapa = "fermentacao" if uso_bf in ("dry hop",) else "fervura"
        ingredientes.append({
            "tipo_ingrediente": "lupulo",
            "name": lupulo.get("name", ""),
            "amount": lupulo.get("amount", 0),
            "unit": "g",
            "time": lupulo.get("time"),
            "use": etapa,
            "uso_detalhado": lupulo.get("use"),
            "cor_ebc": None,
            "rendimento": None,
            "alpha_acidos": lupulo.get("alpha"),
            "atenuacao": None,
        })

    for levedura in recipe_raw.get("yeasts", []) or []:
        ingredientes.append({
            "tipo_ingrediente": "levedura",
            "name": levedura.get("name", ""),
            "amount": levedura.get("amount", 1),
            "unit": levedura.get("unit", "un"),
            "time": None,
            "use": "fermentacao",
            "uso_detalhado": None,
            "cor_ebc": None,
            "rendimento": None,
            "alpha_acidos": None,
            "atenuacao": levedura.get("attenuation"),
        })

    return ingredientes


def _normalizar_mash_steps(recipe_raw: dict) -> list[dict]:
    steps = []
    mash = recipe_raw.get("mash") or {}
    for i, step in enumerate(mash.get("steps", []) or []):
        temperatura = step.get("stepTemp") or step.get("temperature")
        if temperatura is None:
            continue
        steps.append({
            "nome": step.get("name"),
            "temperatura": float(temperatura),
            "tempo_min": step.get("stepTime") or step.get("time"),
            "ramp_time_min": step.get("rampTime"),
            "tipo": (step.get("type") or "temperature").lower(),
            "ordem": i,
        })
    return steps


def _normalizar_fermentation_steps(recipe_raw: dict) -> list[dict]:
    steps = []
    ferm = recipe_raw.get("fermentation") or {}
    for i, step in enumerate(ferm.get("steps", []) or []):
        tempo_raw = step.get("stepTime") or step.get("time")
        temperatura = step.get("stepTemp") or step.get("temperature")
        steps.append({
            "nome": step.get("name"),
            "temperatura": float(temperatura) if temperatura is not None else None,
            "tempo_dias": round(float(tempo_raw) / 1440, 2) if tempo_raw else None,
            "ordem": i,
        })
    return steps


def _get_recipe_detail(recipe_id: str) -> dict:
    """Busca detalhe completo de uma receita (mash steps, fermentation, specs).
    Retorna {} se falhar, sem interromper a sincronização das demais."""
    try:
        return _get(f"/recipes/{recipe_id}")
    except BrewFatherAPIError:
        return {}


def get_recipes(limit: int = _DEFAULT_LIMIT) -> list[dict]:
    """
    Retorna lista de receitas do BrewFather no formato padronizado.
    Busca a lista básica via GET /v2/recipes, depois o detalhe de cada
    receita via GET /v2/recipes/{id} para obter mash steps, fermentation
    steps e specs completos de ingredientes.
    """
    if _is_testing():
        return []

    if not _is_enabled():
        raise BrewFatherDisabledError(
            "Integração BrewFather desabilitada — defina BREWFATHER_ENABLED=True no .env"
        )

    # Lista básica — sem include[], que causava HTTP 500
    raw_list = _get("/recipes", params={"limit": limit})
    if not isinstance(raw_list, list):
        raise BrewFatherAPIError(f"Resposta inesperada da API (esperado lista): {type(raw_list)}")

    result = []
    for r in raw_list:
        recipe_id = r.get("_id", "")
        # Busca detalhe completo para ter mash/fermentation steps e specs
        detail = _get_recipe_detail(recipe_id) if recipe_id else r
        # Se detalhe veio vazio (erro), usa o resumo da lista como fallback
        r_full = detail if detail else r
        result.append({
            "id": recipe_id,
            "name": r_full.get("name") or r.get("name", ""),
            "ingredients": _normalizar_ingredientes(r_full),
            "mash_steps": _normalizar_mash_steps(r_full),
            "fermentation_steps": _normalizar_fermentation_steps(r_full),
        })
    return result
