"""
addons/addon_brewstation/features/feature_yeast_bank/services/yeast_storage_device_service.py

Gerado pelo CrudGen — NÃO editar diretamente. Customizações via hooks
(yeast_storage_device_service_hooks.py, nunca sobrescrito).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from core.db import db
from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_storage_device import YeastStorageDevice

logger = logging.getLogger(__name__)

_READONLY = {"id", "created_at", "updated_at", "is_deleted", "deleted_at"}

try:
    from addons.addon_brewstation.features.feature_yeast_bank.services import yeast_storage_device_service_hooks as _hooks
except ImportError:
    _hooks = None


def _noop(*args, **kwargs):
    return None


def _hook(name):
    return getattr(_hooks, name, _noop) if _hooks else _noop


def _friendly_db_error(exc: Exception) -> str:
    msg = str(exc)
    m = re.search(r"UNIQUE constraint failed:\s*\w+\.(\w+)", msg, re.IGNORECASE)
    if m:
        return f"Já existe um registro com este valor no campo '{m.group(1)}'."
    if "FOREIGN KEY" in msg.upper():
        return "Não é possível excluir: existem registros relacionados."
    return f"Erro ao salvar: {msg.splitlines()[0][:200]}"


@dataclass
class ServiceResult:
    success: bool
    data: Any = None
    error: str | None = None
    code: int = 200


class YeastStorageDeviceService:
    """Camada de negócio para Dispositivo de Armazenamento."""

    def list(self, *, include_deleted: bool = False):
        query = YeastStorageDevice.query
        if not include_deleted:
            query = query.filter(YeastStorageDevice.is_deleted.is_(False))
        return query.order_by(YeastStorageDevice.id.asc()).all()

    def get_by_id(self, id: int) -> "YeastStorageDevice | None":
        return db.session.get(YeastStorageDevice, id)

    def create(self, data: dict) -> ServiceResult:
        obj = YeastStorageDevice()
        self._apply_fields(obj, data)
        db.session.add(obj)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning("Erro ao criar YeastStorageDevice: %s", e)
            return ServiceResult(success=False, error=_friendly_db_error(e), code=422)
        return ServiceResult(success=True, data=obj, code=201)

    def update(self, id: int, data: dict) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Registro não encontrado.", code=404)
        if obj.is_deleted:
            return ServiceResult(success=False, error="Não é possível editar um registro na lixeira.", code=400)
        self._apply_fields(obj, data)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning("Erro ao atualizar YeastStorageDevice id=%s: %s", id, e)
            return ServiceResult(success=False, error=_friendly_db_error(e), code=422)
        return ServiceResult(success=True, data=obj)

    def trash(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Não encontrado.", code=404)
        if obj.is_deleted:
            return ServiceResult(success=False, error="Já está na lixeira.", code=400)
        obj.is_deleted = True
        obj.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def restore(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Não encontrado.", code=404)
        if not obj.is_deleted:
            return ServiceResult(success=False, error="Não está na lixeira.", code=400)
        obj.is_deleted = False
        obj.deleted_at = None
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def delete_permanent(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Não encontrado.", code=404)
        if not obj.is_deleted:
            return ServiceResult(
                success=False,
                error="Apenas registros na lixeira podem ser excluídos permanentemente.",
                code=400,
            )
        db.session.delete(obj)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return ServiceResult(success=False, error=_friendly_db_error(e), code=422)
        return ServiceResult(success=True, data={"id": id})

    def _apply_fields(self, obj, data: dict) -> None:
        data = _hook("pbo_apply_fields")(obj, data) or data
        columns = {c.name: c for c in obj.__table__.columns}
        for key, value in data.items():
            if key in _READONLY or not hasattr(obj, key):
                continue
            value = self._coerce_value(columns.get(key), value)
            setattr(obj, key, value)
        _hook("pai_apply_fields")(obj, data)
        obj.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _coerce_value(column, value):
        """
        Dados de formulário HTML chegam sempre como string — sem isso,
        qualquer coluna boolean levanta `TypeError: Not a boolean
        value: 'true'` ao tentar salvar (bug real encontrado só ao
        testar filtro/checkbox de verdade, não em uso via API JSON,
        que já manda o tipo certo).
        """
        if column is None or not isinstance(value, str):
            return value

        try:
            python_type = column.type.python_type
        except (NotImplementedError, AttributeError):
            return value

        if python_type is bool:
            return value.strip().lower() in ("true", "1", "on", "yes", "sim")
        if python_type is int and value.strip() != "":
            try:
                return int(value)
            except ValueError:
                return value
        if python_type is float and value.strip() != "":
            try:
                return float(value)
            except ValueError:
                return value
        if value == "":
            return None
        return value
