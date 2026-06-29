"""
addons/addon_device_manager/root/services/device_service.py

API pública mínima do addon_device_manager (decisão 2.2 do documento
de arquitetura, docs/skills/05-proposta-addon-device-manager-e-mqtt.md):
get_value / set_value / on_change. Outros Addons (ex.: feature_mash_control)
chamam ESTE service — nunca ORM direto em DeviceActor (skill 02).

Não é gerado pelo CrudGen (assim como device_function_lookup.py, Fase 9)
— é o ponto de extensão estável para a lógica de runtime do Addon.

Onde o valor "atual" fica guardado: dentro de
DeviceActor.config_json["runtime"] (não em coluna própria — é estado
de runtime, não dado de cadastro; evita migration toda vez que o
formato de runtime mudar). Estrutura:

    config_json = {
        "mqtt_config": {...},       # já previsto (seção 4.3 do doc)
        "hardware_mapping": {...},  # já previsto
        "runtime": {
            "last_value": <float|bool|str>,
            "last_seen_at": "<isoformat>",
        },
    }

Logging (Fase D, item pendente fechado em 2026-06-29 — decisão 2.6):
eventos de rotina (valor aceito, valor rejeitado por faixa) vão para
o log de integração local (integration_logger.py), nunca pro log
global — exceto valor fora de faixa, que é "erro que importa" e por
isso sobe TAMBÉM pro log global (logger padrão deste módulo).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from core.db import db
from addons.addon_device_manager.root.model.device_actor import DeviceActor
from addons.addon_device_manager.root.services.integration_logger import get_integration_logger

logger = logging.getLogger(__name__)


# Registro de callbacks em memória (processo local — não persiste, não
# cruza Addons via ORM). Chave: DeviceActor.external_id. Valor: lista
# de callables(new_value).
_on_change_callbacks: dict[str, list] = {}

# Callbacks globais — disparados em TODA mudança de valor, de
# qualquer DeviceActor, não só de um específico. Pensado para o
# motor de automação (feature_mash_control/services/automation_engine.py)
# se inscrever uma única vez no boot e filtrar internamente por
# DeviceFunction.name — device_manager nunca importa mash_control
# (skill 02), é mash_control que se inscreve aqui, na direção
# correta da dependência (mash_control -> device_manager).
_on_any_change_callbacks: list = []


def _resolve_actor(identifier: str) -> DeviceActor | None:
    """
    Resolve um DeviceActor por external_id (preferido, estável) ou por
    name (conveniência). Nunca por id interno — id não é estável para
    uso cross-módulo (skill 02, mesmo espírito da referência fraca por
    name usada em device_function_lookup.py).
    """
    if not identifier:
        return None
    actor = DeviceActor.query.filter_by(external_id=identifier, is_deleted=False).first()
    if actor is None:
        actor = DeviceActor.query.filter_by(name=identifier, is_deleted=False).first()
    return actor


def find_actor_external_id_by_function_name(function_name: str) -> str | None:
    """
    Resolve o external_id do primeiro DeviceActor ativo cuja
    DeviceFunction tenha esse nome — usado por módulos externos (ex.:
    feature_mash_control/automation_engine.py) que só guardam
    referência fraca a `function_name` (skill 02), nunca a um
    DeviceActor específico, e precisam de um identificador aceito por
    get_value()/set_value().

    Limitação conhecida: se mais de um DeviceActor compartilhar a
    mesma function, só o primeiro é retornado — aceitável para o
    volume atual de uso (poucos atores por function); revisar se isso
    se tornar um problema real em produção.
    """
    from addons.addon_device_manager.root.model.device_function import DeviceFunction

    actor = (
        DeviceActor.query
        .join(DeviceFunction, DeviceActor.function_id == DeviceFunction.id)
        .filter(DeviceFunction.name == function_name, DeviceActor.is_deleted.is_(False))
        .first()
    )
    return actor.external_id if actor else None


def _validate_range(actor: DeviceActor, value) -> bool:
    """
    Valida `value` contra DeviceFunction.min_value/max_value (se
    configurados). Sempre retorna True para valor não-numérico ou
    function sem faixa definida — só rejeita quando há faixa E o
    valor numérico está fora dela.
    """
    function = actor.function
    if function is None or (function.min_value is None and function.max_value is None):
        return True
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return True  # não é faixa de número (ex.: bool/string), não se aplica

    if function.min_value is not None and numeric < function.min_value:
        return False
    if function.max_value is not None and numeric > function.max_value:
        return False
    return True


def get_value(identifier: str):
    """Retorna o último valor conhecido (cache) de um DeviceActor, ou None."""
    actor = _resolve_actor(identifier)
    if actor is None:
        return None
    runtime = actor.get_config().get("runtime", {})
    return runtime.get("last_value")


def set_value(identifier: str, value, *, publish: bool = True) -> bool:
    """
    Define o valor de um DeviceActor (tipicamente um atuador).
    Atualiza o cache local sempre; se `publish=True` (default) e o
    cliente MQTT estiver conectado, também publica no command_topic
    configurado em config_json["mqtt_config"]. Retorna False se o
    actor não existir OU se `value` estiver fora da faixa
    (DeviceFunction.min_value/max_value) — um comando fora de faixa
    nunca é aplicado (diferente de update_from_mqtt, que registra a
    leitura mesmo fora de faixa, por ser dado observado, não comando).
    """
    actor = _resolve_actor(identifier)
    if actor is None:
        return False

    if not _validate_range(actor, value):
        logger.error(
            "set_value REJEITADO — valor %r fora da faixa de '%s' (min=%s, max=%s).",
            value, actor.name, actor.function.min_value, actor.function.max_value,
        )
        return False

    config = actor.get_config()
    runtime = config.setdefault("runtime", {})
    runtime["last_value"] = value
    runtime["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    actor.set_config(config)
    db.session.commit()

    get_integration_logger().info("set_value: actor=%s value=%r", actor.name, value)

    _fire_on_change(actor.external_id, value)
    _fire_on_any_change(actor, value)

    if publish:
        _maybe_publish(actor, value)

    return True


def on_any_change(callback) -> None:
    """
    Registra um callback(function_name: str, value) chamado em TODA
    mudança de valor de qualquer DeviceActor — via set_value() ou via
    mensagem MQTT recebida (update_from_mqtt). Recebe `function_name`
    (string, a referência fraca já usada em toda parte — skill 02),
    nunca o objeto DeviceActor em si: quem se inscreve aqui (ex.:
    feature_mash_control/automation_engine.py) nunca deve enxergar
    ORM de outro módulo, mesmo de leitura. Pensado para registro
    único no boot (FeatureMashControl.register_routes() chamando isso
    uma vez), não por instância de actor.
    """
    _on_any_change_callbacks.append(callback)


def on_change(identifier: str, callback) -> bool:
    """
    Registra um callback(new_value) chamado sempre que set_value() (ou
    a recepção de uma mensagem MQTT, via mqtt_client_service) atualizar
    o valor deste DeviceActor. Retorna False se o actor não existir.
    """
    actor = _resolve_actor(identifier)
    if actor is None:
        return False
    _on_change_callbacks.setdefault(actor.external_id, []).append(callback)
    return True


def _fire_on_change(external_id: str, value) -> None:
    for callback in _on_change_callbacks.get(external_id, []):
        callback(value)


def _fire_on_any_change(actor: DeviceActor, value) -> None:
    function_name = actor.function.name if actor.function else None
    for callback in _on_any_change_callbacks:
        try:
            callback(function_name, value)
        except Exception:
            # Um callback de automação com bug nunca pode quebrar a
            # leitura/escrita de device_service em si — log e segue.
            import logging
            logging.getLogger(__name__).exception(
                "Erro em callback on_any_change (actor=%s)", actor.external_id
            )


def _maybe_publish(actor: DeviceActor, value) -> None:
    """
    Publica no broker se o cliente MQTT estiver disponível/conectado.
    Import tardio e best-effort: device_service não pode falhar (nem
    em testes, que não têm broker nenhum) só porque o MQTT está
    desligado — é uma dependência opcional, não obrigatória.
    """
    try:
        from addons.addon_device_manager.root.services import mqtt_client_service
    except ImportError:
        return

    mqtt_config = actor.get_config().get("mqtt_config") or {}
    command_topic = mqtt_config.get("command_topic")
    if not command_topic:
        return

    mqtt_client_service.publish(command_topic, value, qos=mqtt_config.get("qos", 0),
                                 retain=mqtt_config.get("retain", False))


def update_from_mqtt(actor: DeviceActor, value) -> None:
    """
    Chamado pelo mqtt_client_service quando chega uma mensagem em um
    state_topic — atualiza o cache SEM republicar (publish=False),
    para não gerar eco MQTT (publicar de volta o que acabou de chegar).
    Diferente de set_value(): fora de faixa NUNCA é rejeitado aqui —
    é leitura observada de sensor, não comando; rejeitar perderia o
    dado real (que pode ser sintoma de um sensor com defeito, algo
    que vale registrar, não esconder). Só gera log de erro global.
    """
    if not _validate_range(actor, value):
        logger.error(
            "Leitura fora da faixa — actor=%s value=%r (min=%s, max=%s). Valor registrado mesmo assim.",
            actor.name, value, actor.function.min_value, actor.function.max_value,
        )
    else:
        get_integration_logger().info("update_from_mqtt: actor=%s value=%r", actor.name, value)

    config = actor.get_config()
    runtime = config.setdefault("runtime", {})
    runtime["last_value"] = value
    runtime["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    actor.set_config(config)
    db.session.commit()
    _fire_on_change(actor.external_id, value)
    _fire_on_any_change(actor, value)
