"""
addons/addon_brewstation/features/feature_yeast_bank/services/viability_engine.py

Motor de estimativa de viabilidade — portado quase 1:1 de
plugin_yeast_bank/api/routes/yeast_bank_routes.py (BrewStation
original, funções `_compute_estimated_viability` e
`_best_viability_reference_for_item`).

Decisão de correção ao portar (registrada em BACKLOG.md): a ação
opera em LOTE sobre `YeastBankItem` (item físico do banco), usando os
parâmetros de modelo da `YeastStrain` relacionada — nunca foi uma
ação "por cepa". A permissão `recalculate_viability` foi registrada
em `YeastBankItem` (Camada 2), não em `YeastStrain` como uma versão
anterior desta migração tinha feito por engano.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone


def compute_estimated_viability(
    *,
    model_id: str | None,
    reference_viability: float | None,
    days: int | float | None,
    daily_loss_pct: float | None,
    correction_factor: float | None,
    floor_pct: float | None,
) -> float:
    """
    Regra de estimativa de viabilidade.

    `daily_loss_pct` é interpretado como "pontos percentuais/dia" no
    modelo linear (`linear_decay_default`) e como taxa diária
    aproximada (pct/100) no exponencial (`exp_decay`).
    """
    v0 = max(0.0, min(100.0, float(reference_viability or 0.0)))
    days = max(0.0, float(days or 0.0))
    daily_loss_pct = max(0.0, float(daily_loss_pct if daily_loss_pct is not None else 0.35))
    correction_factor = float(correction_factor if correction_factor is not None else 1.0)
    floor_pct = max(0.0, min(100.0, float(floor_pct if floor_pct is not None else 0.0)))
    model_id = (model_id or "linear_decay_default").strip()

    if model_id == "exp_decay":
        k = daily_loss_pct / 100.0
        base = v0 * math.exp(-k * days)
    else:
        base = v0 - (daily_loss_pct * days)

    corrected = base * correction_factor
    corrected = max(floor_pct, min(100.0, corrected))
    return round(corrected, 4)


def best_viability_reference_for_item(item) -> dict | None:
    """
    Busca a melhor referência disponível para um item do banco.

    Prioridade:
    1. Histórico real (`YeastCellCountHistory.viability_percent`) mais recente.
    2. Histórico estimado (`YeastCellCountHistory.estimated_viability_percent`) mais recente.
    3. Starter (`YeastStarterLog.result_viability_percent`) mais recente.
    4. Valor inicial de referência da cepa (`YeastStrain.initial_reference_viability_pct`).

    Todas as consultas excluem registros com `contamination_detected=True`
    — uma leitura contaminada não é uma referência confiável de viabilidade.
    """
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_cell_count_history import YeastCellCountHistory
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_starter_log import YeastStarterLog

    hist_real = (
        YeastCellCountHistory.query
        .filter(
            YeastCellCountHistory.bank_item_id == item.id,
            YeastCellCountHistory.viability_percent.isnot(None),
            YeastCellCountHistory.contamination_detected.is_(False),
        )
        .order_by(YeastCellCountHistory.sample_date.desc(), YeastCellCountHistory.created_at.desc())
        .first()
    )
    if hist_real:
        return {
            "type": "count_history_real",
            "date": hist_real.sample_date or hist_real.created_at.date(),
            "value": hist_real.viability_percent,
        }

    hist_est = (
        YeastCellCountHistory.query
        .filter(
            YeastCellCountHistory.bank_item_id == item.id,
            YeastCellCountHistory.estimated_viability_percent.isnot(None),
            YeastCellCountHistory.contamination_detected.is_(False),
        )
        .order_by(YeastCellCountHistory.sample_date.desc(), YeastCellCountHistory.created_at.desc())
        .first()
    )
    if hist_est:
        return {
            "type": "count_history_estimated",
            "date": hist_est.sample_date or hist_est.created_at.date(),
            "value": hist_est.estimated_viability_percent,
        }

    starter = (
        YeastStarterLog.query
        .filter(
            YeastStarterLog.bank_item_id == item.id,
            YeastStarterLog.result_viability_percent.isnot(None),
            YeastStarterLog.contamination_detected.is_(False),
        )
        .order_by(YeastStarterLog.start_date.desc(), YeastStarterLog.created_at.desc())
        .first()
    )
    if starter:
        return {
            "type": "starter",
            "date": starter.start_date or starter.created_at.date(),
            "value": starter.result_viability_percent,
        }

    strain = item.strain
    if strain and strain.initial_reference_viability_pct is not None:
        return {
            "type": "strain_default",
            "date": item.prepared_date or item.created_at.date(),
            "value": strain.initial_reference_viability_pct,
        }

    return None


_SKIP_STATUSES = {"discarded", "descartado", "retired", "contaminated"}


def recalculate_all(*, today: date | None = None) -> dict:
    """
    Recalcula a viabilidade estimada de TODOS os itens do banco (não é
    uma ação por cepa) — mesmo comportamento do endpoint original
    `POST /viability/recalculate`. Não cria nenhum registro de
    histórico novo; só atualiza os campos de estimativa do próprio
    `YeastBankItem`.
    """
    from core.db import db
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import YeastBankItem

    today = today or datetime.now(timezone.utc).date()

    items = YeastBankItem.query.order_by(YeastBankItem.id.asc()).all()

    processed = 0
    updated = 0
    skipped = 0
    items_without_reference = 0
    details = []

    for item in items:
        processed += 1
        if item.status in _SKIP_STATUSES:
            skipped += 1
            details.append({"item_id": item.id, "status": "skipped", "reason": f"status={item.status}"})
            continue

        ref = best_viability_reference_for_item(item)
        if not ref:
            items_without_reference += 1
            details.append({"item_id": item.id, "status": "no_reference"})
            continue

        strain = item.strain
        days = max(0, (today - ref["date"]).days) if ref.get("date") else 0
        estimated = compute_estimated_viability(
            model_id=(strain.viability_model if strain else None),
            reference_viability=ref.get("value"),
            days=days,
            daily_loss_pct=(strain.daily_viability_loss_pct if strain else None),
            correction_factor=(strain.viability_correction_factor if strain else None),
            floor_pct=(strain.viability_floor_pct if strain else None),
        )

        item.estimated_viability_pct = estimated
        item.estimated_viability_updated_at = datetime.now(timezone.utc)
        item.last_viability_reference_type = ref.get("type")
        item.last_viability_reference_date = ref.get("date")
        item.last_viability_reference_value = ref.get("value")
        updated += 1
        details.append({
            "item_id": item.id,
            "status": "updated",
            "reference_type": ref.get("type"),
            "reference_date": ref.get("date").isoformat() if ref.get("date") else None,
            "reference_value": ref.get("value"),
            "days": days,
            "estimated_viability_pct": estimated,
        })

    db.session.commit()

    return {
        "processed": processed,
        "updated": updated,
        "skipped": skipped,
        "items_without_reference": items_without_reference,
        "today": today.isoformat(),
        "items": details,
    }
