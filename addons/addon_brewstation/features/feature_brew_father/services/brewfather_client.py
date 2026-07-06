"""
addons/addon_brewstation/features/feature_brew_father/services/brewfather_client.py

Cliente da API do BrewFather — stdlib apenas (urllib, base64, json),
sem dependência de requests ou bibliotecas externas, consistente com
o padrão do projeto (ODataConnectionManager, skill 05).

Lê credenciais do .env via os.environ (mesmo padrão de
mqtt_client_service.py que lê MQTT_BROKER_HOST/etc do ambiente).
Credenciais nunca entram em código, nunca em banco.

Guard de TESTING: se TESSERACT_ENV=testing, a chamada real é bloqueada
e retorna lista vazia — evita bateria de testes acionar a API real do
BrewFather com dados reais de produção (o usuário só tem conta de
produção, não existe ambiente de teste).

Lê do .env:
  BREWFATHER_ENABLED=True         # se False/ausente, integração desligada
  BREWFATHER_USER_ID=<user_id>    # username do Basic Auth
  BREWFATHER_API_KEY=<api_key>    # password do Basic Auth
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
        # fora de app_context — assume não-testing (chamada programática direta, rara)
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
    """Chamada GET autenticada. Retorna o JSON decodificado."""
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
    """
    Extrai e normaliza ingredientes de todos os grupos do payload
    de receita do BrewFather (fermentables, hops, yeasts, etc.) para
    o formato que sync_service / ingredient_resolution_service esperam:
    {"name": str, "amount": float, "unit": str, "time": int|None,
     "use": "mash"|"boil"|"fermentation"}.
    """
    ingredientes = []

    for malte in recipe_raw.get("fermentables", []) or []:
        ingredientes.append({
            "name": malte.get("name", ""),
            "amount": malte.get("amount", 0),
            "unit": "kg",
            "time": None,
            "use": "mash",
        })

    for lupulo in recipe_raw.get("hops", []) or []:
        ingredientes.append({
            "name": lupulo.get("name", ""),
            "amount": lupulo.get("amount", 0),
            "unit": "g",
            "time": lupulo.get("time"),
            "use": "boil" if lupulo.get("use", "").lower() in ("boil", "first wort", "flameout") else "fermentation",
        })

    for levedura in recipe_raw.get("yeasts", []) or []:
        ingredientes.append({
            "name": levedura.get("name", ""),
            "amount": levedura.get("amount", 1),
            "unit": levedura.get("unit", "un"),
            "time": None,
            "use": "fermentation",
        })

    return ingredientes


def get_recipes(limit: int = _DEFAULT_LIMIT) -> list[dict]:
    """
    Retorna lista de receitas do BrewFather no formato padronizado
    esperado por sync_service._importar_receita():
    [{"id": str, "name": str, "ingredients": [...]}]

    Guard de TESTING: retorna [] sem acionar a API (nunca chama API
    real em teste — só conta de produção disponível).
    Guard de ENABLED: levanta BrewFatherDisabledError se BREWFATHER_ENABLED!=true.
    """
    if _is_testing():
        return []

    if not _is_enabled():
        raise BrewFatherDisabledError(
            "Integração BrewFather desabilitada — defina BREWFATHER_ENABLED=True no .env"
        )

    raw_list = _get("/recipes", params={"limit": limit})
    if not isinstance(raw_list, list):
        raise BrewFatherAPIError(f"Resposta inesperada da API (esperado lista): {type(raw_list)}")

    return [
        {
            "id": r.get("_id", ""),
            "name": r.get("name", ""),
            "ingredients": _normalizar_ingredientes(r),
        }
        for r in raw_list
    ]
