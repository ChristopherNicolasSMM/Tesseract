"""
addons/addon_brewstation/features/feature_mash_control/services/recipe_timeline_service.py

Timeline única de uma receita (RecipeStep, substitui MashStep —
decisão confirmada em conversa) + geração de Sessão a partir dela
("Importar Receita para Brassar"). NÃO é gerado pelo CrudGen — mesmo
espírito de automation_engine.py/dashboard_runtime_service.py: ponto
de extensão manual estável.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_alarm import BrewSessionAlarm

_VALID_STEP_TYPES = ("mash", "boil", "alert")


class RecipeTimelineError(Exception):
    pass


# ── Timeline da receita (planejamento) ───────────────────────────────────────

def get_timeline(recipe_id: int) -> list[RecipeStep]:
    return (
        RecipeStep.query
        .filter_by(recipe_id=recipe_id, is_deleted=False)
        .order_by(RecipeStep.ordem)
        .all()
    )


def _hop_alert_label(ing: RecipeIngredient) -> str:
    qty = f"{ing.quantidade}{ing.unidade_medida or ''}" if ing.quantidade else ""
    base = f"Lúpulo: {ing.descricao_origem}"
    return f"{base} - {qty}" if qty else base


def sync_hop_alerts(recipe: MashRecipe) -> dict:
    """
    "Toda lupulagem cria alertas" (decisão confirmada em conversa) —
    varre RecipeIngredient (tipo_ingrediente="lupulo", etapa="fervura",
    tempo_adicao_min preenchido — já é convencionalmente "minutos
    restantes de fervura", mesmo significado do `hop_alarms.
    minutes_remaining` do tesseract-device-bridge) e cria/atualiza o
    RecipeStep de alerta correspondente. Idempotente por
    `source_recipe_ingredient_id` — nunca duplica; se a quantidade/
    tempo do ingrediente mudou, atualiza o alerta já existente; se o
    ingrediente sumiu/mudou de etapa, o alerta auto-derivado é
    removido (soft-delete) — alertas manuais nunca são tocados.
    """
    boil_step = (
        RecipeStep.query
        .filter_by(recipe_id=recipe.id, step_type="boil", is_deleted=False)
        .order_by(RecipeStep.ordem)
        .first()
    )

    hop_ingredients = (
        RecipeIngredient.query
        .filter_by(recipe_id=recipe.id, tipo_ingrediente="lupulo", etapa="fervura", is_deleted=False)
        .filter(RecipeIngredient.tempo_adicao_min.isnot(None))
        .all()
    )

    existing_auto = {
        s.source_recipe_ingredient_id: s
        for s in RecipeStep.query.filter_by(
            recipe_id=recipe.id, step_type="alert", source="auto_hop", is_deleted=False,
        ).all()
    }

    created, updated, removed = [], [], []
    seen_ingredient_ids = set()

    for ing in hop_ingredients:
        seen_ingredient_ids.add(ing.id)
        label = _hop_alert_label(ing)
        step = existing_auto.get(ing.id)
        if step:
            if step.nome != label or step.trigger_minutes_remaining != ing.tempo_adicao_min:
                step.nome = label
                step.trigger_minutes_remaining = ing.tempo_adicao_min
                step.parent_step_id = boil_step.id if boil_step else None
                updated.append(label)
        else:
            max_ordem = db.session.query(db.func.max(RecipeStep.ordem)).filter_by(recipe_id=recipe.id).scalar() or 0
            db.session.add(RecipeStep(
                recipe_id=recipe.id, step_type="alert", ordem=max_ordem + 1, nome=label,
                trigger_minutes_remaining=ing.tempo_adicao_min,
                parent_step_id=boil_step.id if boil_step else None,
                source="auto_hop", source_recipe_ingredient_id=ing.id,
            ))
            created.append(label)

    for ing_id, step in existing_auto.items():
        if ing_id not in seen_ingredient_ids:
            step.is_deleted = True
            step.deleted_at = datetime.now(timezone.utc)
            removed.append(step.nome)

    db.session.commit()
    return {"created": created, "updated": updated, "removed": removed}


def add_step(recipe_id: int, *, step_type: str, nome: str, ordem: Optional[int] = None, **fields) -> RecipeStep:
    if step_type not in _VALID_STEP_TYPES:
        raise RecipeTimelineError(f"Tipo de etapa inválido: {step_type}")
    if ordem is None:
        ordem = (db.session.query(db.func.max(RecipeStep.ordem)).filter_by(recipe_id=recipe_id).scalar() or 0) + 1
    allowed_fields = {"temperatura", "tempo_min", "ramp_time_min", "tipo", "trigger_minutes_remaining", "parent_step_id"}
    clean_fields = {k: v for k, v in fields.items() if k in allowed_fields}
    step = RecipeStep(recipe_id=recipe_id, step_type=step_type, nome=nome, ordem=ordem, source="manual", **clean_fields)
    db.session.add(step)
    db.session.commit()
    return step


def update_step(step_id: int, **fields) -> RecipeStep:
    step = RecipeStep.query.get(step_id)
    if not step or step.is_deleted:
        raise RecipeTimelineError("Etapa não encontrada.")
    allowed_fields = {"nome", "temperatura", "tempo_min", "ramp_time_min", "tipo", "trigger_minutes_remaining", "parent_step_id"}
    for key, value in fields.items():
        if key in allowed_fields:
            setattr(step, key, value)
    db.session.commit()
    return step


def remove_step(step_id: int) -> None:
    step = RecipeStep.query.get(step_id)
    if step:
        step.is_deleted = True
        step.deleted_at = datetime.now(timezone.utc)
        db.session.commit()


def reorder_steps(recipe_id: int, ordered_ids: list[int]) -> None:
    steps_by_id = {s.id: s for s in RecipeStep.query.filter_by(recipe_id=recipe_id, is_deleted=False).all()}
    for index, step_id in enumerate(ordered_ids):
        step = steps_by_id.get(step_id)
        if step:
            step.ordem = index
    db.session.commit()


# ── Geração de Sessão a partir da timeline ("lote temporário ou não") ───────

def generate_session_from_recipe(recipe_id: int, *, plant_id: int, name: str, status: str = "draft",
                                  created_by_user_id: Optional[int] = None) -> BrewSession:
    """
    "Gerar Sessão" — RecipeStep (planejamento) é SEMPRE copiado
    (snapshot), nunca referenciado ao vivo, pra BrewSessionStep
    (execução) — igual ao padrão já usado em RecipeHistory (skill 06).
    `status` decide se a sessão nasce "draft" (temporária/revisável,
    sem `started_at`) ou "active" (real, começa agora) — decisão
    confirmada em conversa, reaproveitando o status que já existia.
    """
    if status not in ("draft", "active"):
        raise RecipeTimelineError("Status inicial precisa ser 'draft' ou 'active'.")

    timeline = get_timeline(recipe_id)
    if not timeline:
        raise RecipeTimelineError("Esta receita não tem nenhuma etapa na timeline ainda.")

    started_at = datetime.now(timezone.utc) if status == "active" else None
    session = BrewSession(
        name=name, plant_id=plant_id, recipe_id=recipe_id, status=status, started_at=started_at,
        operator_id=created_by_user_id,
    )
    db.session.add(session)
    db.session.flush()

    cumulative_min = 0.0
    end_offset_by_step_id: dict[int, float] = {}
    step_index = 0

    for step in timeline:
        if step.step_type in ("mash", "boil"):
            ramp = step.ramp_time_min or 0
            hold = step.tempo_min or 0
            cumulative_min += ramp + hold
            end_offset_by_step_id[step.id] = cumulative_min
            db.session.add(BrewSessionStep(
                session_id=session.id, step_index=step_index, name=step.nome or step.step_type,
                step_type=step.step_type, target_temp=step.temperatura,
                duration_seconds=int(hold * 60),
            ))
            step_index += 1

    for step in timeline:
        if step.step_type == "alert":
            parent_end = end_offset_by_step_id.get(step.parent_step_id, cumulative_min)
            trigger_min = parent_end - (step.trigger_minutes_remaining or 0)
            trigger_seconds = max(0, int(trigger_min * 60))
            db.session.add(BrewSessionStep(
                session_id=session.id, step_index=step_index, name=step.nome or "Alerta",
                step_type="alert", duration_seconds=0, trigger_at_seconds=trigger_seconds,
            ))
            step_index += 1

    db.session.commit()
    return session


# ── Disparo automático de alerta (chamado a cada snapshot do Dashboard) ─────

def check_and_fire_alerts(session: BrewSession) -> list[BrewSessionAlarm]:
    """Reaproveita o polling de 3s que a tela do Dashboard já faz —
    sem scheduler novo. Idempotente via `BrewSessionStep.alarm_fired`."""
    if not session.started_at:
        return []

    started_at = session.started_at
    if started_at.tzinfo is not None:
        started_at = started_at.replace(tzinfo=None)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    elapsed_seconds = (now - started_at).total_seconds()

    due_steps = (
        BrewSessionStep.query
        .filter(
            BrewSessionStep.session_id == session.id,
            BrewSessionStep.step_type == "alert",
            BrewSessionStep.alarm_fired.is_(False),
            BrewSessionStep.trigger_at_seconds.isnot(None),
            BrewSessionStep.trigger_at_seconds <= elapsed_seconds,
            BrewSessionStep.is_deleted.is_(False),
        )
        .all()
    )

    fired = []
    for step in due_steps:
        alarm = BrewSessionAlarm(
            session_id=session.id, alarm_type="step_alert", severity="medium",
            message=step.name,
        )
        db.session.add(alarm)
        step.alarm_fired = True
        fired.append(alarm)

    if fired:
        db.session.commit()
    return fired


# ── Ajuste em tempo de execução vira histórico ───────────────────────────────

def adjust_session_step(session_step_id: int, *, field: str, new_value, user_id: Optional[int] = None) -> BrewSessionStep:
    """
    "Posso escolher modificar algum valor em tempo de execução e isso
    salva como ajuste do lote, assim tem histórico" (decisão
    confirmada em conversa) — reaproveita `BrewSessionLog`
    (source="user") em vez de tabela nova, mesmo mecanismo já usado
    pelo logger de leitura de sensor (source="sensor")."""
    allowed_fields = {"target_temp", "duration_seconds", "name"}
    if field not in allowed_fields:
        raise RecipeTimelineError(f"Campo não ajustável: {field}")

    step = BrewSessionStep.query.get(session_step_id)
    if not step or step.is_deleted:
        raise RecipeTimelineError("Passo da sessão não encontrado.")

    old_value = getattr(step, field)
    setattr(step, field, new_value)

    db.session.add(BrewSessionLog(
        session_id=step.session_id, step_id=step.id, source="user", log_level="info",
        message=f"Ajuste manual: {field} de {old_value} para {new_value}",
        detail_json={"field": field, "old_value": old_value, "new_value": new_value, "user_id": user_id},
    ))
    db.session.commit()
    return step
