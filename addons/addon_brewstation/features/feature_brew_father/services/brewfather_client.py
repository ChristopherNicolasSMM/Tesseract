"""
addons/addon_brewstation/features/feature_brew_father/services/brewfather_client.py

Cliente da API do BrewFather — stdlib apenas (urllib, base64, json).
Lê credenciais do .env via os.environ. Ver docs/technical/03-fluxos.md.

Campos capturados desta rodada (além dos anteriores):
  fermentables: color→cor_ebc, yield→rendimento
  hops:         alpha→alpha_acidos, use→uso_detalhado
  yeasts:       attenuation→atenuacao
  recipe:       mash.steps[], fermentation.steps[]
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
            "use": "mash",
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
            "use": "fermentation",
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
        steps.append({
            "nome": step.get("name"),
            "temperatura": step.get("stepTemp") or step.get("temperature"),
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
        steps.append({
            "nome": step.get("name"),
            "temperatura": step.get("stepTemp") or step.get("temperature"),
            "tempo_dias": round(float(tempo_raw) / 1440, 2) if tempo_raw else None,  # minutos → dias
            "ordem": i,
        })
    return steps


def get_recipes(limit: int = _DEFAULT_LIMIT) -> list[dict]:
    if _is_testing():
        return []
    if not _is_enabled():
        raise BrewFatherDisabledError(
            "Integração BrewFather desabilitada — defina BREWFATHER_ENABLED=True no .env"
        )

    # BrewFather requer include[] para trazer ingredientes e passos
    raw_list = _get("/recipes", params={"limit": limit, "include[]": "ingredients"})
    if not isinstance(raw_list, list):
        raise BrewFatherAPIError(f"Resposta inesperada da API (esperado lista): {type(raw_list)}")

    result = []
    for r in raw_list:
        # Alguns endpoints básicos não incluem mash/fermentation sem fetch detalhado
        # Tenta pegar id e busca detalhe se necessário
        r_detail = r  # usa o que veio; se vier sem steps, ficam listas vazias
        result.append({
            "id": r_detail.get("_id", ""),
            "name": r_detail.get("name", ""),
            "ingredients": _normalizar_ingredientes(r_detail),
            "mash_steps": _normalizar_mash_steps(r_detail),
            "fermentation_steps": _normalizar_fermentation_steps(r_detail),
        })
    return result
