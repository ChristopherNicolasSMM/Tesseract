"""
addons/addon_brewstation/features/feature_brew_father/services/sync_service.py

Orquestra a sincronização: busca receitas via brewfather_client e
grava em MashRecipe/RecipeIngredient/RecipeStep/FermentationStep com
origem_receita="BrewFather".
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.db import db
from addons.addon_brewstation.features.feature_brew_father.model.brew_father_sync import BrewFatherSync
from addons.addon_brewstation.features.feature_brew_father.services import brewfather_client
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep
from addons.addon_brewstation.features.feature_mash_control.model.fermentation_step import FermentationStep
from addons.addon_brewstation.features.feature_mash_control.model.water_profile import WaterProfile
from addons.addon_brewstation.features.feature_mash_control.services import ingredient_resolution_service

# Item (c) do BACKLOG.md (decisão fechada): sparge conta como mostura;
# primary/secondary (valores reais de miscs[].use) são fermentação;
# bottling NÃO é mapeado de propósito — ausente daqui, cai no fallback
# (valor bruto da API) em vez de forçado numa etapa que não é.
_USE_PARA_ETAPA = {
    "mash": "mostura",
    "sparge": "mostura",
    "boil": "fervura",
    "fermentation": "fermentacao",
    "primary": "fermentacao",
    "secondary": "fermentacao",
    "dry hop": "fermentacao",
    "whirlpool": "fervura",
    "flameout": "fervura",
    "first wort": "fervura",
}


def sync_recipes() -> dict:
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
        except Exception as exc:  # noqa: BLE001
            erros += 1
            log.mensagem_erro = f"{receita_externa.get('id')}: {exc}"

    log.quantidade_processada = processadas
    log.quantidade_erro = erros
    log.raw_data = _serializar(raw_capturado)
    log.status = "sucesso" if erros == 0 else ("parcial" if processadas > 0 else "erro")
    log.finalizado_em = datetime.now(timezone.utc)
    db.session.commit()

    return log.to_dict()


def listar_receitas_disponiveis() -> list[dict]:
    """
    Skill 27 — listagem enxuta pra tela de seleção prévia (não importa
    nada, só lista + sinaliza status). Cruza cada receita do BrewFather
    com `MashRecipe.origem_receita_id` já conhecidos no Tesseract:

    - "nova": nunca vista aqui.
    - "ja_importada": existe uma MashRecipe ativa (não apagada) com
      esse `origem_receita_id`.
    - "apagada_pendente_reimportar": só existe versão(ões) apagada(s)
      — a correção da skill 25 (seção 3.1) já garante que uma nova
      sincronização recria, aqui é só o rótulo de UI avisando disso.
    """
    receitas = brewfather_client.list_recipes_basico()

    resultado = []
    for r in receitas:
        origem_id = r.get("_id", "")
        ativa = MashRecipe.query.filter_by(
            origem_receita="BrewFather", origem_receita_id=origem_id, is_deleted=False,
        ).first()
        apagada = None
        if not ativa:
            apagada = MashRecipe.query.filter_by(
                origem_receita="BrewFather", origem_receita_id=origem_id, is_deleted=True,
            ).first()

        if ativa:
            status = "ja_importada"
        elif apagada:
            status = "apagada_pendente_reimportar"
        else:
            status = "nova"

        resultado.append({
            "id": origem_id,
            "name": r.get("name", ""),
            "style": (r.get("style") or {}).get("name") if isinstance(r.get("style"), dict) else r.get("style"),
            "type": r.get("type"),
            "status": status,
        })
    return resultado


def sincronizar_selecionadas(origem_ids: list[str]) -> dict:
    """
    Skill 27 — importa só as receitas cujo `id` (do BrewFather) foi
    marcado na tela de seleção. Busca o detalhe completo só delas
    (`get_recipe_normalizado`, uma chamada por id) — nunca a lista
    inteira. Mesmo formato de log (`BrewFatherSync`) de `sync_recipes()`,
    pra aparecer no mesmo histórico.
    """
    log = BrewFatherSync(tipo_sync="recipes", status="em_andamento")
    db.session.add(log)
    db.session.commit()

    processadas = 0
    erros = 0
    raw_capturado = []

    for origem_id in origem_ids:
        try:
            receita_externa = brewfather_client.get_recipe_normalizado(origem_id)
            raw_capturado.append(receita_externa)
            _importar_receita(receita_externa)
            processadas += 1
        except Exception as exc:  # noqa: BLE001
            erros += 1
            log.mensagem_erro = f"{origem_id}: {exc}"

    log.quantidade_processada = processadas
    log.quantidade_erro = erros
    log.raw_data = _serializar(raw_capturado)
    log.status = "sucesso" if erros == 0 else ("parcial" if processadas > 0 else "erro")
    log.finalizado_em = datetime.now(timezone.utc)
    db.session.commit()

    return log.to_dict()


def _importar_receita(receita_externa: dict) -> MashRecipe:
    origem_id = receita_externa["id"]

    # Correção (skill 25, seção 3.1): sem is_deleted=False aqui, uma
    # receita apagada (ou futuramente inativada em massa) continuava
    # sendo encontrada como "já existe" e a sync nunca a reimportava —
    # "apagar pra forçar re-sync" não tinha efeito nenhum antes desta
    # correção.
    ja_existe = MashRecipe.query.filter_by(
        origem_receita="BrewFather", origem_receita_id=origem_id, is_deleted=False,
    ).first()
    if ja_existe is not None:
        return ja_existe

    # Correção adicional (skill 25 — achado ao testar a correção
    # acima): MashRecipe tem UniqueConstraint(name, versao) — uma
    # receita apagada continua ocupando esse par, então reimportar com
    # versao=1 fixo colide (IntegrityError) sempre que o nome bater com
    # uma versão já existente (apagada ou não) do mesmo nome. Resolvido
    # com o mesmo espírito de versionamento imutável já usado pelo
    # resto do model (BACKLOG.md/skill de mash_control: "toda edição
    # salva cria uma nova versão/linha, imutável após criada") — uma
    # reimportação após apagar é tratada como nova versão, não como
    # tentativa de reaproveitar a mesma.
    ultima_versao = db.session.query(
        db.func.max(MashRecipe.versao)
    ).filter_by(name=receita_externa["name"]).scalar()
    proxima_versao = (ultima_versao or 0) + 1

    receita = MashRecipe(
        name=receita_externa["name"],
        versao=proxima_versao,
        origem_receita="BrewFather",
        origem_receita_id=origem_id,
    )
    db.session.add(receita)
    db.session.commit()

    # Ingredientes
    for ingrediente in receita_externa.get("ingredients", []):
        etapa = _USE_PARA_ETAPA.get(
            (ingrediente.get("use") or "").lower(),
            ingrediente.get("use"),
        )
        ingredient_resolution_service.resolver_ingrediente(
            receita.id,
            "BrewFather",
            ingrediente["name"],
            quantidade=ingrediente.get("amount"),
            unidade_medida=ingrediente.get("unit"),
            tempo_adicao_min=ingrediente.get("time"),
            etapa=etapa,
            uso_detalhado=ingrediente.get("uso_detalhado"),
            tipo_ingrediente=ingrediente.get("tipo_ingrediente"),
            cor_ebc=ingrediente.get("cor_ebc"),
            rendimento=ingrediente.get("rendimento"),
            alpha_acidos=ingrediente.get("alpha_acidos"),
            atenuacao=ingrediente.get("atenuacao"),
        )

    # Passos de mostura
    for step_data in receita_externa.get("mash_steps", []):
        if step_data.get("temperatura") is None:
            continue
        db.session.add(RecipeStep(
            recipe_id=receita.id,
            step_type="mash",
            nome=step_data.get("nome"),
            temperatura=step_data["temperatura"],
            tempo_min=step_data.get("tempo_min"),
            ramp_time_min=step_data.get("ramp_time_min"),
            tipo=step_data.get("tipo", "temperature"),
            ordem=step_data.get("ordem", 0),
        ))

    # Etapas de fermentação
    for step_data in receita_externa.get("fermentation_steps", []):
        db.session.add(FermentationStep(
            recipe_id=receita.id,
            nome=step_data.get("nome"),
            temperatura=step_data.get("temperatura"),
            tempo_dias=step_data.get("tempo_dias"),
            ordem=step_data.get("ordem", 0),
        ))

    # Perfis de água (item (c) do BACKLOG.md) — direto, sem de-para
    # (de-para só existe pra ingrediente, que referencia Material).
    # unique(recipe_id, contexto) garantido pelo schema; o client já
    # deduplica por contexto na normalização.
    for perfil in receita_externa.get("water_profiles", []):
        db.session.add(WaterProfile(
            recipe_id=receita.id,
            contexto=perfil["contexto"],
            calcio=perfil.get("calcio"),
            magnesio=perfil.get("magnesio"),
            sodio=perfil.get("sodio"),
            cloreto=perfil.get("cloreto"),
            sulfato=perfil.get("sulfato"),
            bicarbonato=perfil.get("bicarbonato"),
            ph=perfil.get("ph"),
        ))

    db.session.commit()
    return receita


def _serializar(dados: list[dict]) -> str:
    import json
    return json.dumps(dados, ensure_ascii=False)
