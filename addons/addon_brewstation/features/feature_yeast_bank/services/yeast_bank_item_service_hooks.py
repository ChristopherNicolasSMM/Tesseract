"""
addons/addon_brewstation/features/feature_yeast_bank/services/yeast_bank_item_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos
"""

from datetime import datetime, timedelta, timezone

from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import (
    YeastBankItem,
)


def pbo_apply_fields(obj, data):
    """
    PBO = Before Apply.

    Mantido disponível para futuras customizações.

    Não precisamos alterar os dados recebidos aqui para a regra de
    identification, pois a identificação deve ser calculada depois
    que os campos selecionáveis forem aplicados ao objeto.
    """
    return data


def _auto_fill_expiry_date(obj) -> None:
    """
    Preenche `expiry_date` automaticamente a partir de
    `YeastBankConfig.expiry_days` do `storage_type` do item, quando:
    - `expiry_date` ainda está vazio (nunca sobrescreve valor já
      informado manualmente — o auto-preenchimento é só um ponto de
      partida, a pessoa pode sempre ajustar na tela depois);
    - existe `prepared_date` (a partir de quando contar os dias);
    - existe config cadastrada pro `storage_type` do item, com
      `expiry_days` preenchido.

    Decisão do Christopher (2026-08-21): a config por tipo de
    armazenamento passou a alimentar validade + decaimento — ver
    model/yeast_bank_config.py e viability_engine.recalculate_all().
    """
    if obj.expiry_date is not None or obj.prepared_date is None or not obj.storage_type:
        return

    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import (
        YeastBankConfig,
    )

    config = YeastBankConfig.query.filter_by(
        storage_type=obj.storage_type, is_deleted=False,
    ).first()

    if config and config.expiry_days:
        obj.expiry_date = obj.prepared_date + timedelta(days=config.expiry_days)


def pai_apply_fields(obj, data):
    """
    PAI = After Apply.

    Recalcula a identificação física do item do banco depois que
    os campos recebidos do formulário/API já foram aplicados ao objeto.

    A identificação é um campo persistido no banco, mas não é um
    campo editável pelo usuário.
    """
    _auto_fill_expiry_date(obj)

    strain_name = None

    if obj.strain:
        # Usa o @display_field da entidade YeastStrain quando disponível.
        display_field = getattr(obj.strain, "_display_field", "id")
        strain_name = getattr(obj.strain, display_field, None)

        # Fallback seguro.
        if not strain_name:
            strain_name = getattr(obj.strain, "name", None)

        if not strain_name:
            strain_name = f"Strain #{obj.strain_id}"

    container_name = None

    if obj.container:
        display_field = getattr(
            obj.container,
            "_display_field",
            "id",
        )

        container_name = getattr(
            obj.container,
            display_field,
            None,
        )

        if not container_name:
            container_name = getattr(
                obj.container,
                "name",
                None,
            )

        if not container_name:
            container_name = f"Container #{obj.container_id}"

    parts = [
        strain_name,
        obj.storage_slot,
        obj.location,
        container_name,
    ]

    # Remove valores vazios.
    parts = [
        str(value).strip()
        for value in parts
        if value is not None and str(value).strip()
    ]

    obj.identification = " - ".join(parts)[:100]

    return None