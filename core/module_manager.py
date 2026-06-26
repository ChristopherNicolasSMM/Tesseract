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
import sys
from pathlib import Path

from core.db import db
from core.crudgen.table_prefix import apply_table_prefix
from core.permissions_sync import sync_model_permissions
from annotations import get_model_metadata

logger = logging.getLogger(__name__)


def _template_dir_for(obj) -> str | None:
    """
    Pasta de templates de um Addon/Feature — descoberta automática,
    sem precisar de metadado extra no manifesto.

    Dois layouts possíveis (skill 01):
    - Feature: templates/ direto, ao lado do arquivo .py
      (features/feature_[nome]/templates/).
    - Addon: templates/ dentro de root/, ao lado de model/controller/
      services/ (addons/addon_[nome]/root/templates/) — o arquivo
      addon.py fica um nível ABAIXO de root/, então sem checar
      "root/templates" aqui, todo Addon com essa estrutura padrão
      (ex.: addon_device_manager, Fase 6, promoção) nunca teria seus
      templates encontrados pelo Jinja (bug real, corrigido nesta
      fase — não existia caso de teste antes porque addon_brewstation
      nunca populou root/ com conteúdo próprio).
    """
    module_name = type(obj).__module__
    mod = sys.modules.get(module_name)
    if not mod or not getattr(mod, "__file__", None):
        return None
    module_dir = Path(mod.__file__).parent

    root_templates_dir = module_dir / "root" / "templates"
    if root_templates_dir.is_dir():
        return str(root_templates_dir)

    templates_dir = module_dir / "templates"
    return str(templates_dir) if templates_dir.is_dir() else None


class ModuleManager:
    def __init__(self, app):
        self.app = app
        self._registered_modules: dict[str, object] = {}
        self._pending_model_classes: list = []
        self._pending_permission_sync: list = []  # [(model_cls, plural), ...]
        self._pending_transactions: list = []  # [(tx_dict, source_module), ...]
        self._template_dirs: list = []

    def register_module(self, module) -> None:
        """
        Registra um Addon/Plugin já instanciado (vindo de discovery).

        Ordem importante (bug real encontrado na Fase 6, FK cross-Feature
        mash_control -> device_manager): primeiro IMPORTA todos os models
        de TODAS as Features do Addon (declarando suas tabelas com nome
        curto na metadata), e só DEPOIS aplica o prefixo em qualquer um
        deles. Se prefixássemos Feature por Feature (como nas Fases 5/5b),
        uma FK de uma Feature processada depois, apontando para uma
        tabela de uma Feature processada antes, falharia — a string da
        FK ("function.id") não encontraria mais a tabela, já renomeada
        para "tesseract_..._function".

        A sincronização de PERMISSÃO é só enfileirada aqui e executada
        de fato em sync_all_permissions(), chamado DEPOIS de
        create_all_pending_tables() — sync precisa que
        tesseract_permission/tesseract_role já existam.
        """
        logger.debug("Registrando módulo: %r", module)

        module.register_routes(self.app)
        logger.debug("Rotas de %s registradas", module.name)

        if module.module_type != "addon":
            self._registered_modules[module.name] = module
            self._publish_activated(module)
            return

        # ── Passo 1: importar TUDO (core do Addon + todas as Features) ──
        pending: list[tuple[object, str]] = []  # [(model_cls, table_prefix), ...]

        core_models = module.register_models()
        for model_cls in core_models:
            pending.append((model_cls, module.table_prefix))
        logger.debug(
            "%s: %d model(s) de núcleo: %s",
            module.name, len(core_models), [m.__name__ for m in core_models],
        )

        addon_template_dir = _template_dir_for(module)
        if addon_template_dir:
            self._template_dirs.append(addon_template_dir)

        for tx in module.get_transactions():
            self._pending_transactions.append((tx, module.name))

        for feature in module.get_features():
            logger.debug("Registrando feature %s de %s", feature.name, module.name)
            feature.register_routes(self.app)
            feature_models = feature.register_models()
            for model_cls in feature_models:
                pending.append((model_cls, feature.table_prefix))
            logger.debug(
                "%s/%s: %d model(s): %s",
                module.name, feature.name, len(feature_models),
                [m.__name__ for m in feature_models],
            )
            for tx in feature.get_transactions():
                self._pending_transactions.append((tx, module.name))

            feature_template_dir = _template_dir_for(feature)
            if feature_template_dir:
                self._template_dirs.append(feature_template_dir)

        # ── Passo 2: SÓ AGORA aplicar prefixo, com tudo já importado ────
        for model_cls, prefix in pending:
            apply_table_prefix(model_cls, prefix)
            self._pending_permission_sync.append(
                (model_cls, get_model_metadata(model_cls)["plural"])
            )

        self._pending_model_classes.extend(model_cls for model_cls, _ in pending)

        self._registered_modules[module.name] = module
        self._publish_activated(module)

    def _publish_activated(self, module) -> None:
        from core.event_bus import event_bus
        event_bus.publish(
            "core.module.activated",
            module_name=module.name,
            module_type=module.module_type,
        )

    def apply_template_loader(self) -> None:
        """
        Chamado uma vez, depois de TODA a descoberta de Addons —
        monta o ChoiceLoader (core/template_loader.py, Fase 1) com a
        pasta templates/ de cada Addon/Feature coletada durante o
        registro. Sem isso, "{% extends 'core/base.html' %}" dentro
        de um template gerado pelo CrudGen nunca resolve (raiz de
        busca do Jinja só via app.template_folder, por padrão).
        """
        from core.template_loader import build_template_loader

        if not self._template_dirs:
            logger.debug("Nenhum template_dir de Addon/Feature para registrar.")
            return

        self.app.jinja_loader = build_template_loader(self.app, self._template_dirs)
        logger.info(
            "ChoiceLoader montado com %d pasta(s) de template de Addon/Feature.",
            len(self._template_dirs),
        )

    def sync_all_permissions(self) -> None:
        """
        Chamado DEPOIS de create_all_pending_tables() — sincroniza
        Camada 1 + Camada 2 de todo model registrado nesta sessão de
        boot. Idempotente (core/permissions_sync.py), seguro em todo
        boot, não só logo após um `generate`.
        """
        if not self._pending_permission_sync:
            return
        logger.debug(
            "Sincronizando permissões de %d model(s) registrado(s)...",
            len(self._pending_permission_sync),
        )
        for model_cls, plural in self._pending_permission_sync:
            sync_model_permissions(model_cls, plural)

    def sync_all_transactions(self) -> None:
        """
        Chamado DEPOIS de create_all_pending_tables() (precisa de
        tesseract_transaction já criada). Sincroniza as transações
        contribuídas por todo Addon/Feature registrado nesta sessão
        de boot — o catálogo de Core (core/transactions_catalog.py)
        é sincronizado separadamente, em core/app_factory.py.
        """
        from core.transactions_sync import sync_transaction
        from core.db import db as _db

        if not self._pending_transactions:
            return
        logger.debug(
            "Sincronizando %d transação(ões) de módulo(s)...",
            len(self._pending_transactions),
        )
        for tx_data, source_module in self._pending_transactions:
            sync_transaction(tx_data, source_module=source_module, is_standard=False)
        _db.session.commit()

    def discover_and_register_addons(self, addons_dir) -> list[str]:
        """
        Descoberta a partir do disco — escaneia addons_dir por
        addon_*/addon.json, importa addon.py, instancia a classe
        declarada em __module__ (skill 01) e registra.

        Retorna a lista de nomes de Addon registrados.
        """
        import importlib.util
        import json
        from pathlib import Path

        addons_dir = Path(addons_dir)
        registered = []

        if not addons_dir.is_dir():
            logger.debug("Pasta de addons não existe: %s", addons_dir)
            return registered

        for addon_dir in sorted(addons_dir.glob("addon_*")):
            manifest_path = addon_dir / "addon.json"
            addon_py_path = addon_dir / "addon.py"

            if not manifest_path.exists() or not addon_py_path.exists():
                logger.debug("Ignorando %s (sem addon.json ou addon.py)", addon_dir.name)
                continue

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            module_name = f"_tesseract_dynamic_{addon_dir.name}"
            spec = importlib.util.spec_from_file_location(module_name, addon_py_path)
            py_module = importlib.util.module_from_spec(spec)
            # Registrar em sys.modules ANTES de exec_module — sem isso,
            # _template_dir_for() nunca resolve mod.__file__ para a
            # instância de Addon (sys.modules.get(module_name) retorna
            # None), e qualquer Addon top-level com root/templates/
            # próprio (ex.: addon_device_manager, Fase 6 promoção)
            # nunca tem seus templates encontrados pelo Jinja. Bug
            # latente desde sempre — nunca disparou porque nenhum
            # Addon tinha conteúdo próprio em root/ até esta fase.
            sys.modules[module_name] = py_module
            spec.loader.exec_module(py_module)

            class_name = getattr(py_module, "__module__", None)
            if not class_name or not hasattr(py_module, class_name):
                logger.warning(
                    "%s: __module__ não declarado ou classe não encontrada — ignorando.",
                    addon_dir.name,
                )
                continue

            addon_class = getattr(py_module, class_name)
            addon_instance = addon_class(manifest)

            self.register_module(addon_instance)
            registered.append(addon_instance.name)
            logger.info("Addon descoberto e registrado: %s", addon_instance.name)

        return registered

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
