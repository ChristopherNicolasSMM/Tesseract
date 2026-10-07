"""Regras manuais do YeastBank, chamadas pelos overrides do CrudGen.

Web/API usam a mesma transação. Eventos não movimentam estoque; lixeira de
histórico não desfaz um descarte físico. Não editar os services gerados.
"""
from __future__ import annotations

import importlib
import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone

from flask import has_request_context
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from core.db import db
from annotations import get_field_labels

logger = logging.getLogger(__name__)
_BASE = 'addons.addon_brewstation.features.feature_yeast_bank'
_ENTITIES = {
    'strain': ('yeast_strain', 'YeastStrain'),
    'device': ('yeast_storage_device', 'YeastStorageDevice'),
    'container': ('yeast_container', 'YeastContainer'),
    'item': ('yeast_bank_item', 'YeastBankItem'),
    'event': ('yeast_bank_event', 'YeastBankEvent'),
    'count': ('yeast_cell_count_history', 'YeastCellCountHistory'),
    'config': ('yeast_bank_config', 'YeastBankConfig'),
}
_PERCENTAGES = {
    'viability_percent', 'estimated_viability_percent', 'result_viability_percent',
    'estimated_viability_pct', 'initial_reference_viability_pct',
    'viability_floor_pct', 'alert_min_viability_pct', 'daily_viability_loss_pct',
}
_NONNEGATIVE = {
    'cells_counted_live', 'cells_counted_dead', 'cells_per_ml',
    'viable_cells_per_ml', 'estimated_cells_per_ml', 'expiry_days',
    'alert_days_before_expiry', 'viability_correction_factor',
}
_POSITIVE = {'squares_counted', 'dilution_factor', 'target_volume_l'}
_RAW = ('cells_counted_live', 'cells_counted_dead', 'squares_counted', 'dilution_factor')
_RESULTS = ('cells_per_ml', 'viability_percent', 'viable_cells_per_ml')


@dataclass
class Result:
    success: bool
    data: object = None
    error: str | None = None
    code: int = 200


class RuleError(ValueError):
    def __init__(self, message, code=422):
        super().__init__(message)
        self.code = code


def model(kind):
    module, name = _ENTITIES[kind]
    return getattr(importlib.import_module(f'{_BASE}.model.{module}'), name)


def _service(kind):
    module, name = _ENTITIES[kind]
    return getattr(importlib.import_module(f'{_BASE}.services.{module}_service'), name + 'Service')()


def _parent(kind, ident):
    cls = model(kind)
    if not isinstance(ident, int) or isinstance(ident, bool) or ident <= 0:
        raise RuleError('Selecione uma referência válida.')
    obj = db.session.get(cls, ident)
    if obj is None or obj.is_deleted:
        raise RuleError('A referência selecionada não existe ou está na lixeira.')
    if kind == 'container':
        _parent('device', obj.device_id)
    if kind == 'item':
        _parent('strain', obj.strain_id)
        _parent('container', obj.container_id)
    return obj


def _validate_scalars(obj):
    labels = get_field_labels(type(obj))
    for column in obj.__table__.columns:
        label = labels.get(column.name, column.name)
        value = getattr(obj, column.name)
        if value is None:
            continue  # defaults do model são aplicados no flush
        expected = column.type.python_type
        if expected is int:
            valid = isinstance(value, int) and not isinstance(value, bool)
        elif expected is float:
            valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        elif expected is date:
            valid = isinstance(value, date) and not isinstance(value, datetime)
        else:
            valid = isinstance(value, expected)
        if not valid:
            raise RuleError(f'Valor inválido para {label}.')
        if column.name in _PERCENTAGES and not 0 <= value <= 100:
            raise RuleError(f'{label} deve estar entre 0 e 100.')
        if column.name in _NONNEGATIVE and value < 0:
            raise RuleError(f'{label} não pode ser negativo.')
        if column.name in _POSITIVE and value <= 0:
            raise RuleError(f'{label} deve ser maior que zero.')
    if hasattr(obj, 'prepared_date') and obj.prepared_date and obj.expiry_date and obj.expiry_date < obj.prepared_date:
        raise RuleError('A validade não pode ser anterior ao preparo.')


def _validate(kind, obj):
    _validate_scalars(obj)
    if kind in ('strain', 'device', 'container') and not (obj.name or '').strip():
        raise RuleError('Nome é obrigatório.')
    if kind == 'container':
        _parent('device', obj.device_id)
    elif kind == 'item':
        _parent('strain', obj.strain_id)
        _parent('container', obj.container_id)
        if not obj.storage_type:
            raise RuleError('Tipo de armazenamento é obrigatório.')
        if obj.status is not None and obj.status not in ('active', 'discarded', 'contaminated'):
            raise RuleError('Status do item inválido.')
    elif kind in ('event', 'count'):
        _parent('item', obj.bank_item_id)
        if kind == 'event':
            if obj.event_type not in ('Starter', 'Contagem de Células', 'Descarte', 'Outro'):
                raise RuleError('Tipo do evento inválido.')
            if obj.starter_status is not None and obj.starter_status not in ('planned', 'active', 'completed', 'discarded'):
                raise RuleError('Status do starter inválido.')
            if obj.status_after is not None and obj.status_after not in ('active', 'discarded', 'contaminated'):
                raise RuleError('Status posterior inválido.')
        elif obj.bank_event_id:
            event = _parent('event', obj.bank_event_id)
            if event.event_type != 'Contagem de Células' or event.bank_item_id != obj.bank_item_id:
                raise RuleError('A contagem deve permanecer no item do evento de origem.')
    elif kind == 'config':
        if not obj.storage_type:
            raise RuleError('Tipo de armazenamento é obrigatório.')
        conflict = model('config').query.filter_by(storage_type=obj.storage_type, is_deleted=False)
        if obj.id:
            conflict = conflict.filter(model('config').id != obj.id)
        if conflict.first():
            raise RuleError('Já existe configuração ativa para este tipo. Revise a configuração ou a lixeira.')


def _guard_event_edit(obj, before):
    # Identidade imutável: não migrar contagens ou descartar outro item ao editar.
    for field in ('bank_item_id', 'event_type'):
        if getattr(obj, field) != before[field]:
            raise RuleError('Item e tipo de evento registrado não podem ser alterados. Crie outro evento.')
    if obj.event_type == 'Descarte' and obj.status_after != before['status_after']:
        raise RuleError('O efeito de descarte já foi registrado; o status posterior não pode ser alterado.')


def _create_event_effects(obj):
    if obj.event_type == 'Contagem de Células':
        if has_request_context() and (not current_user.is_authenticated or not current_user.has_permission('yeast_cell_count_histories.create')):
            raise RuleError('Sem permissão para criar a contagem vinculada.', 403)
        count = model('count')(bank_item_id=obj.bank_item_id, bank_event_id=obj.id)
        db.session.add(count)
        db.session.flush()
        obj.cell_count_id = count.id
    elif obj.event_type == 'Descarte':
        item = _parent('item', obj.bank_item_id)
        if obj.status_after == 'active':
            raise RuleError('Descarte não pode reativar uma cultura.')
        obj.status_before = item.status
        obj.status_after = obj.status_after or 'discarded'
        item.status = obj.status_after
        item.discarded_at = datetime.now(timezone.utc)
        item.discard_reason = obj.notes
    elif obj.event_type == 'Starter' and obj.starter_status is None:
        # Novos registros exigem conclusão explícita; antigos sem status são legados.
        obj.starter_status = 'planned'


def _children(kind, obj, *, include_deleted=False):
    refs = {
        'strain': [('item', 'strain_id')],
        'device': [('container', 'device_id')],
        'container': [('item', 'container_id')],
        'item': [('event', 'bank_item_id'), ('count', 'bank_item_id')],
        'event': [('count', 'bank_event_id')],
        'count': [('event', 'cell_count_id')],
    }
    for child_kind, fk in refs.get(kind, []):
        cls = model(child_kind)
        query = cls.query.filter(getattr(cls, fk) == obj.id)
        if not include_deleted:
            query = query.filter(cls.is_deleted.is_(False))
        if query.first():
            return True
    return False


def operate(kind, action, ident=None, data=None):
    """Override completo: captura falhas de aplicação, flush e commit."""
    cls = model(kind)
    try:
        if action == 'create':
            obj = cls()
        else:
            obj = db.session.get(cls, ident)
            if obj is None:
                return Result(False, error='Registro não encontrado.', code=404)
        if action in ('create', 'update'):
            if action == 'update' and obj.is_deleted:
                raise RuleError('Não é possível editar um registro na lixeira.', 400)
            if not isinstance(data, dict):
                raise RuleError('Dados inválidos.')
            before = {column.name: getattr(obj, column.name) for column in obj.__table__.columns}
            # Nunca aceitar relationships pelo JSON; defaults/readonly continuam no gerador.
            fields = {key: value for key, value in data.items() if key in obj.__table__.columns}
            with db.session.no_autoflush:
                _service(kind)._apply_fields(obj, fields)
                _validate(kind, obj)
                if action == 'update':
                    if kind == 'event':
                        _guard_event_edit(obj, before)
                    if kind == 'count':
                        changed = any(getattr(obj, key) != before[key] for key in _RAW)
                        stale = any(before[key] is not None and fields.get(key, before[key]) not in ('', None) and getattr(obj, key) == before[key] for key in _RESULTS)
                        if changed and stale:
                            raise RuleError('Ao alterar a entrada bruta, limpe os três resultados para recalcular ou informe os resultados revisados.')
            if action == 'create':
                db.session.add(obj)
                db.session.flush()
                if kind == 'event':
                    _create_event_effects(obj)
        elif action == 'trash':
            if obj.is_deleted:
                raise RuleError('Já está na lixeira.', 400)
            # Histórico do item/evento pode ir à lixeira sem destruir registros físicos.
            if kind in ('strain', 'device', 'container') and _children(kind, obj):
                raise RuleError('Existem registros ativos vinculados. Envie os dependentes à lixeira primeiro.')
            obj.is_deleted = True
            obj.deleted_at = datetime.now(timezone.utc)
        elif action == 'restore':
            if not obj.is_deleted:
                raise RuleError('Não está na lixeira.', 400)
            with db.session.no_autoflush:
                _validate(kind, obj)
            obj.is_deleted = False
            obj.deleted_at = None
        elif action == 'delete_permanent':
            if not obj.is_deleted:
                raise RuleError('Apenas registros na lixeira podem ser excluídos permanentemente.', 400)
            if _children(kind, obj, include_deleted=True):
                raise RuleError('Existem referências históricas. Preserve o registro na lixeira.')
            db.session.delete(obj)
        else:
            raise RuleError('Operação desconhecida.')
        db.session.commit()
        return Result(True, data={'id': ident} if action == 'delete_permanent' else obj, code=201 if action == 'create' else 200)
    except RuleError as exc:
        db.session.rollback()
        return Result(False, error=str(exc), code=exc.code)
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return Result(False, error=str(exc), code=422)
    except IntegrityError:
        db.session.rollback()
        logger.warning('Conflito de integridade YeastBank %s/%s', kind, action)
        return Result(False, error='Conflito com registro existente ou relacionado. Revise o cadastro.', code=422)
    except Exception:
        db.session.rollback()
        logger.exception('Falha na operação YeastBank %s/%s', kind, action)
        return Result(False, error='Não foi possível salvar. Nenhuma alteração foi confirmada.', code=422)
