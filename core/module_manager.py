"""
core/module_manager.py

Responsável por: descoberta de manifestos em disco, registro de
models/rotas, ativação/desativação (estado persistido em
tesseract_module_state), e criação de tabelas.

Decisão de arquitetura (Opção B, ver conversa): nenhuma "múltiplas
passadas" de criação de tabela. A ordem certa é simples — descobrir e
IMPORTAR todos os models de todos os módulos ativos ANTES de chamar
db.create_all() uma única vez. O SQLAlchemy resolve a ordem de FK
sozinho via topological sort em metadata.sorted_tables. Isso só
funciona porque a skill 02 já proíbe FK entre Addons diferentes — o
grafo de dependência que sobra (Feature -> core do próprio Addon,
qualquer -> tesseract_user) é pequeno e nunca cíclico.

Em dev (LOG_LEVEL=DEBUG), cada etapa de discovery/registro/criação é
logada — rastreabilidade alta de propósito para facilitar debug.
"""
import logging

from core.db import db

logger = logging.getLogger(__name__)


class ModuleManager:
    def __init__(self, app):
        self.app = app
        self._registered_modules: dict[str, object] = {}
        self._pending_model_classes: list = []

    def register_module(self, module) -> None:
        """
        Registra um Addon/Plugin já instanciado (vindo de discovery).
        Não cria tabela aqui — só acumula os models pendentes.
        """
        logger.debug("Registrando módulo: %r", module)

        module.register_routes(self.app)
        logger.debug("Rotas de %s registradas", module.name)

        if module.module_type == "addon":
            models = module.register_models()
            logger.debug(
                "%s: %d model(s) pendente(s) de criação: %s",
                module.name, len(models), [m.__name__ for m in models],
            )
            self._pending_model_classes.extend(models)

        self._registered_modules[module.name] = module

        from core.event_bus import event_bus
        event_bus.publish(
            "core.module.activated",
            module_name=module.name,
            module_type=module.module_type,
        )

    def create_all_pending_tables(self) -> None:
        """
        Chamada uma única vez, depois que TODOS os módulos ativos já
        foram registrados (ver app_factory.py). Opção B: sem loop de
        passadas — só garante que os models estão no metadata e deixa
        o SQLAlchemy ordenar.

        Importante: db.create_all() roda sempre, mesmo com 0 Addons
        ativos — ele cria TODAS as tabelas presentes no metadata
        compartilhado, incluindo as de Core (tesseract_module_state,
        tesseract_system_config), que não passam por
        _pending_model_classes (essa lista é só dos models trazidos
        por Addons, para fins de log).
        """
        if self._pending_model_classes:
            logger.info(
                "Criando tabelas de %d model(s) de Addon (%d módulo(s) "
                "ativo(s))...",
                len(self._pending_model_classes), len(self._registered_modules),
            )
            for model_cls in self._pending_model_classes:
                logger.debug(
                    "  -> %s (tabela: %s)",
                    model_cls.__name__, getattr(model_cls, "__tablename__", "?"),
                )
        else:
            logger.debug(
                "Nenhum model de Addon pendente — ainda assim chamando "
                "create_all() para garantir as tabelas de Core."
            )

        db.create_all()
        logger.info("Tabelas criadas/verificadas com sucesso.")

    @property
    def active_modules(self) -> dict:
        return dict(self._registered_modules)
