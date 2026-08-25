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

from datetime import date, datetime, timedelta, timezone


def compute_alert_flags(item, today: date | None = None) -> dict:
    """
    Reanálise de eventos (2026-08-24, decisão do Christopher): os
    limites de `YeastBankConfig.alert_days_before_expiry`/
    `alert_min_viability_pct` só viram um sinalizador pra tela mostrar
    — não criam `YeastBankEvent` nem qualquer outra ação automática.

    Calculado sob demanda (não persistido) — sempre reflete o estado
    atual do item/config no momento em que é chamado, nunca fica
    desatualizado entre recálculos.

    `next_starter_days`/`next_starter_date` (Painel, 2026-08-24):
    estimativa de quando a viabilidade estimada vai cruzar
    `alert_min_viability_pct`, usando o mesmo decaimento diário que
    `recalculate_all()` usa (config do storage_type, com fallback pra
    cepa) — decisão do Christopher: "com base na configuração de
    alerta". Não é um agendamento real, é só a extrapolação linear de
    quando a viabilidade cruzaria o limite se nada for feito — pensada
    como sugestão de quando vale a pena propagar (fazer um starter)
    pra manter a cepa saudável.
    """
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import (
        YeastBankConfig,
    )

    today = today or datetime.now(timezone.utc).date()
    flags = {
        "expiry_alert": False,
        "low_viability_alert": False,
        "next_starter_days": None,
        "next_starter_date": None,
    }

    config = YeastBankConfig.query.filter_by(
        storage_type=item.storage_type, is_deleted=False,
    ).first()
    if not config:
        return flags

    if config.alert_days_before_expiry is not None and item.expiry_date:
        days_left = (item.expiry_date - today).days
        flags["expiry_alert"] = days_left <= config.alert_days_before_expiry

    if config.alert_min_viability_pct is not None and item.estimated_viability_pct is not None:
        flags["low_viability_alert"] = item.estimated_viability_pct <= config.alert_min_viability_pct

        strain = item.strain
        daily_loss_pct = config.daily_viability_loss_pct
        if daily_loss_pct is None and strain:
            daily_loss_pct = strain.daily_viability_loss_pct

        if daily_loss_pct and daily_loss_pct > 0:
            dias = (item.estimated_viability_pct - config.alert_min_viability_pct) / daily_loss_pct
            dias = int(dias)  # trunca — "faltam N dias" não arredonda pra cima
            flags["next_starter_days"] = max(dias, 0)  # já vencido o limite -> 0 ("agora")
            flags["next_starter_date"] = (today + timedelta(days=max(dias, 0))).isoformat()
    return flags


def compute_estimated_viability(
    *,
    reference_viability: float | None,
    days: int | float | None,
    daily_loss_pct: float | None,
    correction_factor: float | None,
    floor_pct: float | None,
) -> float:
    """
    Regra de estimativa de viabilidade — sempre linear (o modelo
    exponencial foi removido: nunca funcionou de verdade, ver
    model/yeast_strain.py; opção travada em "só linear" por decisão
    do Christopher em vez de consertar o mapeamento de opções).
    """
    v0 = max(0.0, min(100.0, float(reference_viability or 0.0)))
    days = max(0.0, float(days or 0.0))
    daily_loss_pct = max(0.0, float(daily_loss_pct if daily_loss_pct is not None else 0.35))
    correction_factor = float(correction_factor if correction_factor is not None else 1.0)
    floor_pct = max(0.0, min(100.0, float(floor_pct if floor_pct is not None else 0.0)))

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
    3. Starter (`YeastBankEvent.result_viability_percent`, `event_type="Starter"` — skill 22, campo fundido do antigo `YeastStarterLog`) mais recente.
    4. Valor inicial de referência da cepa (`YeastStrain.initial_reference_viability_pct`).

    Todas as consultas excluem registros com `contamination_detected=True`
    — uma leitura contaminada não é uma referência confiável de viabilidade.
    """
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_cell_count_history import YeastCellCountHistory
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_event import YeastBankEvent

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
        YeastBankEvent.query
        .filter(
            YeastBankEvent.bank_item_id == item.id,
            YeastBankEvent.event_type == "Starter",
            YeastBankEvent.result_viability_percent.isnot(None),
            YeastBankEvent.contamination_detected.is_(False),
        )
        .order_by(YeastBankEvent.start_date.desc(), YeastBankEvent.created_at.desc())
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


_SKIP_STATUSES = {"discarded", "contaminated"}  # valores canônicos — enum corrigido (achado real, reanálise de eventos)


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
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import YeastBankConfig

    today = today or datetime.now(timezone.utc).date()

    items = YeastBankItem.query.order_by(YeastBankItem.id.asc()).all()

    # Config por storage_type — carregada uma vez, indexada pelo tipo.
    # Christopher decidiu (2026-08-21): quando existe config pro
    # storage_type do item, o % de decaimento dela SUBSTITUI o da
    # cepa (ignora daily_viability_loss_pct da YeastStrain nesse
    # caso) — correction_factor/floor_pct continuam vindo da cepa,
    # só o decaimento em si é trocado.
    configs_by_type = {
        c.storage_type: c
        for c in YeastBankConfig.query.filter(YeastBankConfig.is_deleted.is_(False)).all()
    }

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
        config = configs_by_type.get(item.storage_type)
        if config is not None and config.daily_viability_loss_pct is not None:
            daily_loss_pct = config.daily_viability_loss_pct
        else:
            daily_loss_pct = strain.daily_viability_loss_pct if strain else None

        days = max(0, (today - ref["date"]).days) if ref.get("date") else 0
        estimated = compute_estimated_viability(
            reference_viability=ref.get("value"),
            days=days,
            daily_loss_pct=daily_loss_pct,
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
