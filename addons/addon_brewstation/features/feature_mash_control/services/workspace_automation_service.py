"""Operações manuais da Automação no workspace; não gerado pelo CrudGen."""
from datetime import datetime, timezone
import math

from core.db import db
from addons.addon_device_manager.root.services.device_function_lookup import get_function_by_name
from addons.addon_brewstation.features.feature_mash_control.model.automation_rule import AutomationRule
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession


class WorkspaceAutomationError(ValueError):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code


def scoped_rule(plant_id, rule_id):
    plant = db.session.get(BrewPlant, plant_id)
    rule = db.session.get(AutomationRule, rule_id)
    if not plant or plant.is_deleted or not rule:
        raise WorkspaceAutomationError('Planta ou regra não encontrada.', 404)
    if rule.session_id is not None:
        session = db.session.get(BrewSession, rule.session_id)
        if not session or session.is_deleted or session.plant_id != plant_id:
            raise WorkspaceAutomationError('Regra não encontrada nesta planta.', 404)
    return rule


_LABELS = {'name': 'nome', 'description': 'descrição', 'sensor_metric': 'métrica do sensor',
           'condition_unit': 'unidade exibida', 'sensor_function_name': 'sensor',
           'actor_function_name': 'atuador', 'condition_value': 'valor da condição',
           'actor_value': 'valor da ação', 'cooldown_seconds': 'intervalo entre disparos'}


def _number(data, field, *, integer=False, optional=False):
    raw = str(data.get(field, '')).strip()
    if optional and not raw:
        return None
    try:
        value = int(raw) if integer else float(raw)
    except (ValueError, TypeError):
        raise WorkspaceAutomationError('Informe um valor numérico válido para ' + _LABELS[field] + '.')
    if (integer and (value < 0 or value > 2147483647)) or (not integer and not math.isfinite(value)):
        raise WorkspaceAutomationError('Valor fora do intervalo permitido: ' + _LABELS[field] + '.')
    return value


def save_rule(plant_id, data, rule_id=None):
    plant = db.session.get(BrewPlant, plant_id)
    if not plant or plant.is_deleted:
        raise WorkspaceAutomationError('Planta não encontrada.', 404)
    rule = scoped_rule(plant_id, rule_id) if rule_id is not None else AutomationRule(is_active=False)
    if rule.is_deleted or rule.is_active:
        raise WorkspaceAutomationError('Desative a regra antes de editar; regras na lixeira não podem ser editadas.')
    values = {}
    for field, maximum, required in [('name', 200, True), ('description', 1000, False),
                                      ('sensor_metric', 50, False), ('condition_unit', 20, False)]:
        value = str(data.get(field, '')).strip()
        if (required and not value) or len(value) > maximum:
            raise WorkspaceAutomationError('Informe ' + _LABELS[field] + ' dentro do tamanho permitido.')
        values[field] = value or None
    for field, category in [('sensor_function_name', 'sensor'), ('actor_function_name', 'actuator')]:
        name = str(data.get(field, '')).strip()
        function = get_function_by_name(name)
        if len(name) > 100 or not function or function.get('category') not in (category, 'hybrid'):
            raise WorkspaceAutomationError('Selecione uma função disponível e compatível para ' + _LABELS[field] + '.')
        values[field] = name
    operator = data.get('condition_operator')
    action = data.get('actor_action')
    if operator not in ('<=', '>=', '==', '!=', '<', '>') or action not in ('ON', 'OFF', 'TOGGLE', 'SET_VALUE'):
        raise WorkspaceAutomationError('Selecione condição e ação válidas.')
    values.update(condition_operator=operator, actor_action=action,
                  condition_value=_number(data, 'condition_value'),
                  actor_value=_number(data, 'actor_value', optional=action != 'SET_VALUE'),
                  cooldown_seconds=_number(data, 'cooldown_seconds', integer=True))
    raw_session = str(data.get('session_id', '')).strip()
    session = None
    if raw_session:
        try:
            session = db.session.get(BrewSession, int(raw_session))
        except ValueError:
            pass
        if not session or session.is_deleted or session.plant_id != plant_id:
            raise WorkspaceAutomationError('Selecione uma sessão desta planta.')
    values['session_id'] = session.id if session else None
    for field, value in values.items():
        setattr(rule, field, value)
    db.session.add(rule)
    db.session.commit()
    return rule


def maintain_rule(plant_id, rule_id, action):
    rule = scoped_rule(plant_id, rule_id)
    if action == 'restore':
        if rule.is_deleted:
            rule.is_deleted = False
            rule.deleted_at = None
            rule.is_active = False
    elif action == 'trash':
        if not rule.is_deleted:
            rule.is_active = False
            rule.is_deleted = True
            rule.deleted_at = datetime.now(timezone.utc)
    elif action in ('activate', 'deactivate'):
        if rule.is_deleted:
            raise WorkspaceAutomationError('Restaure a regra antes de alterar seu status.')
        if action == 'activate':
            # Confere condição/ação de regras antigas; preserva contador/horário.
            data = {field: getattr(rule, field) for field in ('name', 'description', 'sensor_metric',
                    'condition_unit', 'sensor_function_name', 'actor_function_name', 'condition_operator',
                    'actor_action', 'condition_value', 'actor_value', 'cooldown_seconds', 'session_id')}
            # Ativação não reaplica campos nem confirma transação intermediária.
            for field, category in [('sensor_function_name', 'sensor'), ('actor_function_name', 'actuator')]:
                function = get_function_by_name(data[field])
                if not function or function.get('category') not in (category, 'hybrid'):
                    raise WorkspaceAutomationError('Funções indisponíveis ou incompatíveis.')
            if data['condition_operator'] not in ('<=', '>=', '==', '!=', '<', '>') or data['actor_action'] not in ('ON', 'OFF', 'TOGGLE', 'SET_VALUE'):
                raise WorkspaceAutomationError('Condição ou ação inválida.')
            _number(data, 'condition_value')
            if data['actor_action'] == 'SET_VALUE':
                _number(data, 'actor_value')
            if data['cooldown_seconds'] is not None:
                _number(data, 'cooldown_seconds', integer=True)
            from addons.addon_brewstation.features.feature_mash_control.services.automation_engine import _plant_allows_functions
            if not _plant_allows_functions(rule):
                raise WorkspaceAutomationError('Confira mapeamentos exclusivos e um único ator por função antes de ativar.')
        rule.is_active = action == 'activate'
    else:
        raise WorkspaceAutomationError('Ação inválida.')
    db.session.commit()
    return rule
