"""
addons/addon_brewstation/features/feature_brew_father/services/sync_service.py

Orquestra a sincronização: busca receitas via brewfather_client
(mock nesta rodada), grava em MashRecipe/RecipeIngredient
(feature_mash_control) com origem_receita="BrewFather", delegando a
resolução de ingrediente pra ingredient_resolution_service (nunca
duplica essa lógica aqui — é reaproveitável por futuras integrações,
ex.: feature_beersmith).

Limitação desta rodada, registrada e não escondida: uma receita
externa (mesmo origem_receita_id) só é importada UMA VEZ — sync
repetido não cria nova versão nem detecta mudança no BrewFather. Ver
docs/technical/03-fluxos.md, pendências.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.db import db
from addons.addon_brewstation.features.feature_brew_father.model.brew_father_sync import BrewFatherSync
from addons.addon_brewstation.features.feature_brew_father.services import brewfather_client
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.services import ingredient_resolution_service

_USE_PARA_ETAPA = {
    "mash": "mostura",
    "boil": "fervura",
    "fermentation": "fermentacao",
}


def sync_recipes() -> dict:
    """
    Sincroniza receitas do BrewFather. Retorna o BrewFatherSync
    (dict) resultante, com status "sucesso" | "erro" | "parcial".
    """
    log = BrewFatherSync(tipo_sync="recipes", status="em_andamento")
    db.session.add(log)
    db.session.commit()

    processadas = 0
    erros = 0
    raw_capturado = []

    try:
        receitas_externas = brewfather_client.get_recipes()
    except brewfather_client.BrewFatherDisabledError as exc:
        log.status = "erro"
        log.mensagem_erro = str(exc)
        log.finalizado_em = datetime.now(timezone.utc)
        db.session.commit()
        return log.to_dict()
    except brewfather_client.BrewFatherAPIError as exc:
        log.status = "erro"
        log.mensagem_erro = str(exc)
        log.finalizado_em = datetime.now(timezone.utc)
        db.session.commit()
        return log.to_dict()

    for receita_externa in receitas_externas:
        raw_capturado.append(receita_externa)
        try:
            _importar_receita(receita_externa)
            processadas += 1
        except Exception as exc:  # noqa: BLE001 - captura ampla proposital: erro em uma receita não pode derrubar a sincronização inteira
            erros += 1
            log.mensagem_erro = f"{receita_externa.get('id')}: {exc}"

    log.quantidade_processada = processadas
    log.quantidade_erro = erros
    log.raw_data = _serializar(raw_capturado)
    log.status = "sucesso" if erros == 0 else ("parcial" if processadas > 0 else "erro")
    log.finalizado_em = datetime.now(timezone.utc)
    db.session.commit()

    return log.to_dict()


def _importar_receita(receita_externa: dict) -> MashRecipe:
    origem_id = receita_externa["id"]

    ja_existe = MashRecipe.query.filter_by(
        origem_receita="BrewFather", origem_receita_id=origem_id,
    ).first()
    if ja_existe is not None:
        return ja_existe  # limitação desta rodada: não re-sincroniza, ver docstring do módulo

    receita = MashRecipe(
        name=receita_externa["name"],
        versao=1,
        origem_receita="BrewFather",
        origem_receita_id=origem_id,
    )
    db.session.add(receita)
    db.session.commit()

    for ingrediente in receita_externa.get("ingredients", []):
        ingredient_resolution_service.resolver_ingrediente(
            receita.id,
            "BrewFather",
            ingrediente["name"],
            quantidade=ingrediente.get("amount"),
            unidade_medida=ingrediente.get("unit"),
            tempo_adicao_min=ingrediente.get("time"),
            etapa=_USE_PARA_ETAPA.get(ingrediente.get("use"), ingrediente.get("use")),
        )

    return receita


def _serializar(dados: list[dict]) -> str:
    import json
    return json.dumps(dados, ensure_ascii=False)
