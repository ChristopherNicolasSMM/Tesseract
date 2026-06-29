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
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.db import db
from addons.addon_device_manager.root.model.device_actor import DeviceActor


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
    actor não existir.
    """
    actor = _resolve_actor(identifier)
    if actor is None:
        return False

    config = actor.get_config()
    runtime = config.setdefault("runtime", {})
    runtime["last_value"] = value
    runtime["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    actor.set_config(config)
    db.session.commit()

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
    """
    config = actor.get_config()
    runtime = config.setdefault("runtime", {})
    runtime["last_value"] = value
    runtime["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    actor.set_config(config)
    db.session.commit()
    _fire_on_change(actor.external_id, value)
    _fire_on_any_change(actor, value)
