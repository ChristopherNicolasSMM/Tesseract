"""
addons/addon_brewstation/features/feature_brew_father/services/brewfather_client.py

Cliente da API do BrewFather. Nesta rodada, implementação MOCK — sem
credenciais reais, retorna dados fixos pra exercitar o fluxo de
sincronização/resolução de ingrediente de ponta a ponta. Troca por
chamada HTTP real é só reimplementar o corpo de `get_recipes()`
(mesma assinatura, mesmo formato de retorno) — nenhum outro arquivo
precisa mudar.

Formato de retorno de `get_recipes()`: lista de dicts com:
  {
      "id": str (id externo do BrewFather),
      "name": str,
      "ingredients": [
          {"name": str, "amount": float, "unit": str,
           "time": int | None, "use": "mash" | "boil" | "fermentation"},
          ...
      ],
  }
"""
from __future__ import annotations

MOCK_RECIPES = [
    {
        "id": "bf-mock-001",
        "name": "Sangue de Druida",
        "ingredients": [
            {"name": "Pale Malt 2-Row", "amount": 5.0, "unit": "kg", "time": None, "use": "mash"},
            {"name": "Cascade", "amount": 0.05, "unit": "kg", "time": 60, "use": "boil"},
            {"name": "US-05", "amount": 1.0, "unit": "un", "time": None, "use": "fermentation"},
        ],
    },
    {
        "id": "bf-mock-002",
        "name": "Session IPA Tropical",
        "ingredients": [
            {"name": "Pilsner Malt", "amount": 4.2, "unit": "kg", "time": None, "use": "mash"},
            {"name": "Citra", "amount": 0.08, "unit": "kg", "time": 15, "use": "boil"},
        ],
    },
]


class BrewFatherAPIError(Exception):
    pass


def get_recipes() -> list[dict]:
    """MOCK — substituir por chamada real (GET /recipes) quando as
    credenciais (BREWFATHER_USER_ID/BREWFATHER_API_KEY) estiverem
    disponíveis."""
    return MOCK_RECIPES
