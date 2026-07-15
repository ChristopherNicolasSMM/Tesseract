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
                duration_seconds=int(hold * 60), ramp_seconds=int(ramp * 60),
                source_recipe_step_id=step.id,
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
                source_recipe_step_id=step.id,
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


# ── Etapa atual/próxima no Dashboard de Brassagem (conversa — Ponto 2) ──────
#
# Opção confirmada em conversa: o operador edita a RECEITA-MODELO
# (RecipeStep) direto pelo Dashboard — reaproveitando add_step/update_step
# já existentes — e usa resync_session_steps() pra refletir a mudança na
# sessão em execução (mesmo espírito de sync_hop_alerts, generalizado pra
# mash/boil/alert). Nunca mexe em passo já active/completed/skipped —
# histórico de execução já começado é imutável.

_LOCKED_STEP_STATUSES = ("active", "completed", "skipped")


def _operational_steps_query(session_id: int):
    return (
        BrewSessionStep.query
        .filter_by(session_id=session_id, is_deleted=False)
        .filter(BrewSessionStep.step_type.in_(("mash", "boil")))
        .order_by(BrewSessionStep.step_index)
    )


def resync_session_steps(session_id: int) -> dict:
    """Ressincroniza BrewSessionStep com a timeline atual de RecipeStep.
    Só adiciona passo novo (RecipeStep sem BrewSessionStep correspondente),
    atualiza passo `pending` cujo RecipeStep de origem mudou, e remove
    (soft-delete) passo `pending` cujo RecipeStep de origem sumiu da
    timeline. Passo sem `source_recipe_step_id` (sessão gerada antes desta
    coluna existir) nunca é tocado — fica como "órfão" intencionalmente."""
    session = BrewSession.query.get(session_id)
    if not session or session.is_deleted:
        raise RecipeTimelineError("Sessão não encontrada.")
    if not session.recipe_id:
        raise RecipeTimelineError("Esta sessão não tem receita associada.")

    timeline = get_timeline(session.recipe_id)
    existing = BrewSessionStep.query.filter_by(session_id=session.id, is_deleted=False).all()
    existing_by_source = {s.source_recipe_step_id: s for s in existing if s.source_recipe_step_id}

    # Mesmo cálculo de deslocamento acumulado de generate_session_from_recipe
    # — só usado pra dar duration_seconds/trigger_at_seconds corretos a
    # passo NOVO; passo pending já existente mantém seu step_index (ordem
    # de execução em andamento não é reordenada por um resync).
    cumulative_min = 0.0
    end_offset_by_step_id: dict[int, float] = {}
    for step in timeline:
        if step.step_type in ("mash", "boil"):
            cumulative_min += (step.ramp_time_min or 0) + (step.tempo_min or 0)
            end_offset_by_step_id[step.id] = cumulative_min

    next_step_index = max((s.step_index for s in existing), default=-1) + 1
    created, updated, removed = [], [], []
    seen_recipe_step_ids = set()

    for step in timeline:
        if step.step_type not in ("mash", "boil", "alert"):
            continue
        seen_recipe_step_ids.add(step.id)
        session_step = existing_by_source.get(step.id)
        if session_step and session_step.status in _LOCKED_STEP_STATUSES:
            continue  # histórico já em execução/concluído — nunca mexe

        if step.step_type in ("mash", "boil"):
            new_name = step.nome or step.step_type
            new_target = step.temperatura
            new_duration = int((step.tempo_min or 0) * 60)
            new_ramp = int((step.ramp_time_min or 0) * 60)
        else:
            parent_end = end_offset_by_step_id.get(step.parent_step_id, cumulative_min)
            trigger_min = parent_end - (step.trigger_minutes_remaining or 0)
            new_name = step.nome or "Alerta"
            new_trigger = max(0, int(trigger_min * 60))

        if session_step:
            changed = False
            if session_step.name != new_name:
                session_step.name = new_name
                changed = True
            if step.step_type in ("mash", "boil"):
                if session_step.target_temp != new_target:
                    session_step.target_temp = new_target
                    changed = True
                if session_step.duration_seconds != new_duration:
                    session_step.duration_seconds = new_duration
                    changed = True
                if session_step.ramp_seconds != new_ramp:
                    session_step.ramp_seconds = new_ramp
                    changed = True
            elif session_step.trigger_at_seconds != new_trigger:
                session_step.trigger_at_seconds = new_trigger
                changed = True
            if changed:
                updated.append(new_name)
            continue

        kwargs = dict(
            session_id=session.id, step_index=next_step_index, name=new_name,
            step_type=step.step_type, source_recipe_step_id=step.id,
        )
        if step.step_type in ("mash", "boil"):
            kwargs.update(target_temp=new_target, duration_seconds=new_duration, ramp_seconds=new_ramp)
        else:
            kwargs.update(duration_seconds=0, trigger_at_seconds=new_trigger)
        db.session.add(BrewSessionStep(**kwargs))
        next_step_index += 1
        created.append(new_name)

    for source_id, session_step in existing_by_source.items():
        if source_id not in seen_recipe_step_ids and session_step.status not in _LOCKED_STEP_STATUSES:
            session_step.is_deleted = True
            session_step.deleted_at = datetime.now(timezone.utc)
            removed.append(session_step.name)

    db.session.commit()
    return {"created": created, "updated": updated, "removed": removed}


def _ensure_current_step_active(session: BrewSession) -> None:
    """Promove preguiçosamente o primeiro passo `pending` pra `active`
    assim que a sessão está em execução e nenhum passo operacional
    (mash/boil) está ativo ainda — "start" implícito do passo 1,
    disparado na primeira leitura do card (mesmo padrão de
    check_and_fire_alerts: reaproveita o polling do snapshot, sem
    scheduler novo)."""
    if session.status != "active":
        return
    steps = _operational_steps_query(session.id).all()
    if any(s.status == "active" for s in steps):
        return
    first_pending = next((s for s in steps if s.status == "pending"), None)
    if first_pending:
        first_pending.status = "active"
        first_pending.started_at = datetime.now(timezone.utc)
        db.session.commit()


def go_back_step(session_id: int) -> dict:
    """"Voltar" do card de Etapa (conversa — inspirado no controle
    prev/next do painel de referência): desfaz o avanço, devolvendo a
    etapa atual pra `pending` (zera timer) e reativando a etapa anterior
    `completed` com o timer reiniciado do zero — é um "refazer esta
    etapa", não uma reconstrução exata do tempo já gasto antes."""
    session = BrewSession.query.get(session_id)
    if not session or session.is_deleted:
        raise RecipeTimelineError("Sessão não encontrada.")

    steps = _operational_steps_query(session.id).all()
    current = next((s for s in steps if s.status == "active"), None)
    if current:
        previous = next(
            (s for s in reversed(steps) if s.status == "completed" and s.step_index < current.step_index),
            None,
        )
    else:
        previous = next((s for s in reversed(steps) if s.status == "completed"), None)

    if not previous:
        raise RecipeTimelineError("Não há etapa anterior pra voltar.")

    now = datetime.now(timezone.utc)
    if current:
        current.status = "pending"
        current.started_at = None
        current.completed_at = None
        current.actual_duration_s = None

    previous.status = "active"
    previous.started_at = now
    previous.completed_at = None
    previous.actual_duration_s = None

    db.session.commit()
    return get_step_card_data(session)


def confirm_and_advance_step(session_id: int) -> dict:
    """"Concluir e Avançar" do card de Etapa (conversa — modelo híbrido:
    o timer só sugere quando a etapa terminou, esta confirmação explícita
    é quem de fato conclui e já avança pra próxima, num clique só). Botão
    fica sempre disponível — nada aqui valida se o tempo já passou."""
    session = BrewSession.query.get(session_id)
    if not session or session.is_deleted:
        raise RecipeTimelineError("Sessão não encontrada.")

    _ensure_current_step_active(session)
    steps = _operational_steps_query(session.id).all()
    current = next((s for s in steps if s.status == "active"), None)
    if not current:
        raise RecipeTimelineError("Não há etapa ativa pra concluir.")

    now = datetime.now(timezone.utc)
    current.status = "completed"
    current.completed_at = now
    started = current.started_at
    if started:
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        current.actual_duration_s = max(0, int((now - started).total_seconds()))

    next_step = next((s for s in steps if s.status == "pending" and s.step_index > current.step_index), None)
    if next_step:
        next_step.status = "active"
        next_step.started_at = now

    db.session.commit()
    return get_step_card_data(session)


def get_step_card_data(session: Optional[BrewSession]) -> dict:
    """Dado consumido pelo widget `step_card` do Dashboard: etapa atual
    (com as DUAS fases — rampa até a temperatura alvo, depois hold/
    patamar — decisão da conversa: rampa some quando termina, hold
    assume) e preview da próxima. `session=None` (sem sessão ativa pra
    planta) devolve tudo vazio — widget mostra estado "sem sessão
    ativa"."""
    if not session:
        return {"current": None, "next": None}

    _ensure_current_step_active(session)
    steps = _operational_steps_query(session.id).all()
    current = next((s for s in steps if s.status == "active"), None)

    def _phase_progress(step: BrewSessionStep) -> dict:
        ramp_s = step.ramp_seconds or 0
        hold_s = step.duration_seconds or 0
        total = ramp_s + hold_s
        if not step.started_at:
            return {
                "phase": "ramp" if ramp_s else "hold",
                "ramp_progress_pct": 0.0, "hold_progress_pct": 0.0,
                "remaining_seconds": total,
            }
        started = step.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()

        if ramp_s and elapsed < ramp_s:
            return {
                "phase": "ramp",
                "ramp_progress_pct": round(max(0.0, min(100.0, (elapsed / ramp_s) * 100)), 1),
                "hold_progress_pct": 0.0,
                "remaining_seconds": max(0, int(total - elapsed)),
            }
        hold_elapsed = elapsed - ramp_s
        hold_pct = 100.0 if not hold_s else max(0.0, min(100.0, (hold_elapsed / hold_s) * 100))
        return {
            "phase": "hold",
            "ramp_progress_pct": 100.0,
            "hold_progress_pct": round(hold_pct, 1),
            "remaining_seconds": max(0, int(total - elapsed)),
        }

    current_out = None
    if current:
        current_out = {
            "id": current.id, "name": current.name, "step_type": current.step_type,
            "target_temp": current.target_temp, "duration_seconds": current.duration_seconds,
            "ramp_seconds": current.ramp_seconds,
            **_phase_progress(current),
        }
        next_step = next((s for s in steps if s.status == "pending" and s.step_index > current.step_index), None)
    else:
        next_step = next((s for s in steps if s.status == "pending"), None)

    next_out = None
    if next_step:
        next_out = {
            "id": next_step.id, "name": next_step.name, "step_type": next_step.step_type,
            "target_temp": next_step.target_temp, "duration_seconds": next_step.duration_seconds,
            "ramp_seconds": next_step.ramp_seconds,
        }

    return {"current": current_out, "next": next_out}
