from __future__ import annotations

from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import (
    YeastStrain,
)
from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_storage_device import (
    YeastStorageDevice,
)
from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import (
    YeastBankItem,
)
from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_container import (
    YeastContainer,
)


def get_yeast_strain(strain_id: int | None) -> dict | None:
    if not strain_id:
        return None

    obj = YeastStrain.query.filter_by(
        id=strain_id,
        is_deleted=False,
    ).first()

    if not obj:
        return None

    data = obj.to_dict()

    display_field = getattr(YeastStrain, "_display_field", "id")
    data["display"] = (
        getattr(obj, display_field, None)
        or f"Cepa #{obj.id}"
    )

    return data


def get_yeast_storage_device(device_id: int | None) -> dict | None:
    if not device_id:
        return None

    obj = YeastStorageDevice.query.filter_by(
        id=device_id,
        is_deleted=False,
    ).first()

    if not obj:
        return None

    data = obj.to_dict()

    display_field = getattr(YeastStorageDevice, "_display_field", "id")
    data["display"] = (
        getattr(obj, display_field, None)
        or f"Dispositivo #{obj.id}"
    )

    return data


def get_yeast_container(container_id: int | None) -> dict | None:
    if not container_id:
        return None

    obj = YeastContainer.query.filter_by(
        id=container_id,
        is_deleted=False,
    ).first()

    if not obj:
        return None

    data = obj.to_dict()

    display_field = getattr(YeastContainer, "_display_field", "id")
    data["display"] = (
        getattr(obj, display_field, None)
        or f"Container #{obj.id}"
    )

    return data


def get_yeast_bank_item(bank_item_id: int | None) -> dict | None:
    if not bank_item_id:
        return None

    obj = YeastBankItem.query.filter_by(
        id=bank_item_id,
        is_deleted=False,
    ).first()

    if not obj:
        return None

    data = obj.to_dict()

    display_field = getattr(
        YeastBankItem,
        "_display_field",
        "id",
    )

    data["display"] = (
        getattr(obj, display_field, None)
        or f"Item do Banco #{obj.id}"
    )

    return data