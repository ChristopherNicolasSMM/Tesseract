"""
addons/addon_brewstation/features/feature_brew_father/services/sync_service.py

Orquestra a sincronização: busca receitas via brewfather_client e
grava em MashRecipe/RecipeIngredient/RecipeStep/FermentationStep com
origem_receita="BrewFather".
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

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


def sync_recipes(*, ressincronizar: bool = False) -> dict:
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
            _importar_receita(receita_externa, ressincronizar=ressincronizar)
            processadas += 1
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
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

    return _classificar_receitas(receitas)


def _classificar_receitas(receitas: list[dict]) -> list[dict]:
    ids = [r.get("_id") for r in receitas if r.get("_id")]
    estados: dict[str, str] = {}
    if ids:
        existentes = MashRecipe.query.filter(
            MashRecipe.origem_receita == "BrewFather",
            MashRecipe.origem_receita_id.in_(ids),
        ).all()
        for existente in existentes:
            origem_id = existente.origem_receita_id
            if not origem_id:
                continue
            if not existente.is_deleted:
                estados[origem_id] = "ja_importada"
            elif estados.get(origem_id) != "ja_importada":
                estados[origem_id] = "apagada_pendente_reimportar"

    def tags_da_receita(raw):
        tags = raw.get("tags") or []
        if not isinstance(tags, list):
            return []
        return [tag.get("display") or tag.get("value") if isinstance(tag, dict) else tag
                for tag in tags if isinstance(tag, (dict, str))]

    return [{
        "id": r["_id"],
        "name": r.get("name") or "Sem nome",
        "style": (r.get("style") or {}).get("name") if isinstance(r.get("style"), dict) else r.get("style"),
        "type": r.get("type"),
        "path": r.get("path") if isinstance(r.get("path"), str) and r["path"] else "/",
        "tags": [tag for tag in tags_da_receita(r) if isinstance(tag, str) and tag],
        "status": estados.get(r["_id"], "nova"),
    } for r in receitas if r.get("_id")]


def listar_portal_receitas(filtros: dict[str, str], *, atualizar: bool = False) -> dict:
    """Lista as páginas disponíveis e aplica filtros locais antes da seleção."""
    raw, limitado = brewfather_client.list_recipes_portal_cached(force=atualizar)
    todas = _classificar_receitas(raw)
    q = (filtros.get("q") or "").strip().casefold()
    estilo = filtros.get("estilo") or ""
    tipo = filtros.get("tipo") or ""
    status = filtros.get("status") or ""
    pasta = filtros.get("pasta") or ""
    tag = filtros.get("tag") or ""
    filtradas = [r for r in todas if (
        (not q or q in r["name"].casefold())
        and (not estilo or r["style"] == estilo)
        and (not tipo or r["type"] == tipo)
        and (not status or r["status"] == status)
        and (not pasta or r["path"] == pasta or
             (pasta != "/" and r["path"].startswith(pasta.rstrip("/") + "/")))
        and (not tag or tag in r["tags"])
    )]
    return {
        "receitas": filtradas,
        "total": len(todas),
        "limitado": limitado,
        "estilos": sorted({r["style"] for r in todas if r["style"]}),
        "tipos": sorted({r["type"] for r in todas if r["type"]}),
        "pastas": sorted({r["path"] for r in todas}),
        "tags": sorted({tag for r in todas for tag in r["tags"]}),
    }


def listar_portal_lotes(filtros: dict[str, str], *, atualizar: bool = False) -> dict:
    status = filtros.get("status") or ""
    raw, limitado = brewfather_client.list_portal_cached("batches", status=status, force=atualizar)
    q = (filtros.get("q") or "").strip().casefold()
    todos = [{
        "id": r["_id"], "name": r.get("name") or "Sem nome",
        "batch_no": r.get("batchNo"), "status": r.get("status") or "—",
        "brew_date": _formatar_data_bf(r.get("brewDate")),
        "recipe": (r.get("recipe") or {}).get("name") if isinstance(r.get("recipe"), dict) else None,
    } for r in raw if isinstance(r, dict) and r.get("_id")]
    exibidos = [r for r in todos if not q or q in r["name"].casefold() or q in (r["recipe"] or "").casefold()]
    return {"lotes": exibidos, "total": len(todos), "limitado": limitado}


def _formatar_data_bf(value) -> str:
    if value in (None, ""):
        return "—"
    try:
        if isinstance(value, (int, float)):
            seconds = value / 1000 if abs(value) >= 10**11 else value
            return datetime.fromtimestamp(seconds, timezone.utc).strftime("%d/%m/%Y")
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except (ValueError, TypeError, OverflowError, OSError):
        return str(value)


def _tem_saldo_brewfather(value) -> bool:
    try:
        return Decimal(str(value)) > 0
    except (InvalidOperation, ValueError, TypeError):
        return False


def listar_portal_inventario(categoria: str, filtros: dict[str, str], *, atualizar: bool = False) -> dict:
    raw, limitado = brewfather_client.list_portal_cached(categoria, force=atualizar)
    todos = [{
        "id": r["_id"], "name": r.get("name") or "Sem nome",
        "type": r.get("type") or "—", "supplier": r.get("supplier") or "—",
        "inventory": r.get("inventory"),
        "has_stock": _tem_saldo_brewfather(r.get("inventory")),
    } for r in raw if isinstance(r, dict) and r.get("_id")]
    q = (filtros.get("q") or "").strip().casefold()
    stock = filtros.get("stock") or ""
    exibidos = [r for r in todos if (
        (not q or q in r["name"].casefold() or q in r["supplier"].casefold())
        and (not stock or r["has_stock"] == (stock == "positive"))
    )]
    return {"itens": exibidos, "total": len(todos), "limitado": limitado,
            "categorias": {"fermentables": "Fermentáveis", "hops": "Lúpulos",
                           "yeasts": "Leveduras", "miscs": "Outros ingredientes"}}


def sincronizar_selecionadas(origem_ids: list[str], *, ressincronizar: bool = False,
                            limite: int = 50) -> dict:
    """
    Skill 27 — importa só as receitas cujo `id` (do BrewFather) foi
    marcado na tela de seleção. Busca o detalhe completo só delas
    (`get_recipe_normalizado`, uma chamada por id) — nunca a lista
    inteira. Mesmo formato de log (`BrewFatherSync`) de `sync_recipes()`,
    pra aparecer no mesmo histórico.
    """
    origem_ids = list(dict.fromkeys(id.strip() for id in origem_ids if id.strip()))
    if not origem_ids or len(origem_ids) > limite:
        raise ValueError(f"Selecione de 1 a {limite} receitas por sincronização.")
    if ressincronizar:
        existentes = {row[0] for row in db.session.query(MashRecipe.origem_receita_id).filter(
            MashRecipe.origem_receita == "BrewFather", MashRecipe.is_deleted.is_(False),
            MashRecipe.origem_receita_id.in_(origem_ids),
        ).all()}
        if set(origem_ids) != existentes:
            raise ValueError("Ressincronize somente receitas já importadas e ativas.")

    log = BrewFatherSync(tipo_sync="recipes", status="em_andamento")
    db.session.add(log)
    db.session.commit()

    processadas = 0
    erros = 0
    raw_capturado = []

    for origem_id in origem_ids:
        try:
            receita_externa = brewfather_client.get_recipe_normalizado(origem_id)
            if receita_externa.get("id") != origem_id:
                raise ValueError("O detalhe retornado não corresponde à receita solicitada.")
            raw_capturado.append(receita_externa)
            _importar_receita(receita_externa, ressincronizar=ressincronizar)
            processadas += 1
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            erros += 1
            log.mensagem_erro = f"{origem_id}: {exc}"

    log.quantidade_processada = processadas
    log.quantidade_erro = erros
    log.raw_data = _serializar(raw_capturado)
    log.status = "sucesso" if erros == 0 else ("parcial" if processadas > 0 else "erro")
    log.finalizado_em = datetime.now(timezone.utc)
    db.session.commit()

    return log.to_dict()


def ressincronizar_todas_importadas() -> dict:
    """Atualiza todas as receitas ativas locais, sem importar receitas novas."""
    ids = [row[0] for row in db.session.query(MashRecipe.origem_receita_id).filter_by(
        origem_receita="BrewFather", is_deleted=False,
    ).distinct().all() if row[0]]
    if not ids:
        raise ValueError("Não há receitas importadas para ressincronizar.")
    if len(ids) > 500:
        raise ValueError("Há mais de 500 receitas importadas. Selecione grupos menores para respeitar o limite da API.")
    return sincronizar_selecionadas(ids, ressincronizar=True, limite=500)


def apagar_receitas_importadas(origem_ids: list[str] | None = None) -> int:
    """Move somente receitas Brewfather para a lixeira, sem tocar nos lotes."""
    query = MashRecipe.query.filter_by(origem_receita="BrewFather", is_deleted=False)
    if origem_ids is not None:
        ids = list(dict.fromkeys(i.strip() for i in origem_ids if i.strip()))
        if not ids:
            raise ValueError("Selecione ao menos uma receita importada.")
        query = query.filter(MashRecipe.origem_receita_id.in_(ids))
    receitas = query.all()
    agora = datetime.now(timezone.utc)
    for receita in receitas:
        receita.is_deleted = True
        receita.deleted_at = agora
    db.session.commit()
    return len(receitas)


def _importar_receita(receita_externa: dict, *, ressincronizar: bool = False) -> MashRecipe:
    origem_id = receita_externa["id"]

    # Correção (skill 25, seção 3.1): sem is_deleted=False aqui, uma
    # receita apagada (ou futuramente inativada em massa) continuava
    # sendo encontrada como "já existe" e a sync nunca a reimportava —
    # "apagar pra forçar re-sync" não tinha efeito nenhum antes desta
    # correção.
    versoes_ativas = MashRecipe.query.filter_by(
        origem_receita="BrewFather", origem_receita_id=origem_id, is_deleted=False,
    ).all()
    ja_existe = versoes_ativas[0] if versoes_ativas else None
    if ja_existe is not None and not ressincronizar:
        return ja_existe

    # A versão antiga e os seus vínculos permanecem consultáveis.
    # A troca é feita na mesma transação que cria a nova versão; uma
    # falha na importação reverte a marcação de lixeira.
    if versoes_ativas:
        agora = datetime.now(timezone.utc)
        for versao in versoes_ativas:
            versao.is_deleted = True
            versao.deleted_at = agora

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
    db.session.flush()

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
            commit=False,
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
