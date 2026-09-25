"""
addons/addon_brewstation/features/feature_envase/services/envase_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos
"""

from datetime import date

from addons.addon_brewstation.features.feature_envase.services import envase_estoque_service


def create_override(data):
    # O formulário gerado e a API compartilham a mesma regra de confirmação.
    from addons.addon_brewstation.features.feature_envase.services.envase_service import ServiceResult
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    from core.db import db

    try:
        lote_id = int(data["lote_id"])
        material_id = int(data["material_resultante_id"])
        quantidade = float(str(data["quantidade_litros"]).replace(",", "."))
        data_envase = data.get("data_envase") or None
        if isinstance(data_envase, str):
            data_envase = date.fromisoformat(data_envase)
        if data_envase is not None and not isinstance(data_envase, date):
            raise ValueError("Data de envase inválida.")
        resultado = envase_estoque_service.registrar_envase(
            lote_id, material_id, quantidade,
            data_envase=data_envase, tipo_envase=data.get("tipo_envase") or None,
        )
    except (KeyError, TypeError, ValueError, envase_estoque_service.LoteNaoEncontradoError,
            envase_estoque_service.MaterialNaoEncontradoError,
            envase_estoque_service.VolumeRealNaoConfiguradoError) as exc:
        db.session.rollback()
        return ServiceResult(success=False, error=f"Envase não confirmado: {exc}", code=422)
    return ServiceResult(success=True, data=db.session.get(Envase, resultado["envase"]["id"]), code=201)


def _immutable(*_args):
    from addons.addon_brewstation.features.feature_envase.services.envase_service import ServiceResult
    return ServiceResult(success=False, error="Envase confirmado: corrija por um fluxo de estorno rastreável.", code=409)


update_override = _immutable
trash_override = _immutable
restore_override = _immutable
delete_permanent_override = _immutable
