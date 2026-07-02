"""
core/module_base.py

Classe abstrata comum a Addon e Plugin (skill 00, termo "Module").
Nenhum Addon/Plugin herda diretamente daqui — sempre via AddonBase ou
PluginBase, que impõem a regra de tabela (skill 00/02).
"""
from abc import ABC


class ModuleBase(ABC):
    name: str
    label: str
    version: str
    module_type: str  # "addon" | "plugin" — nunca setado direto, ver subclasses

    def __init__(self, manifest: dict):
        self.manifest = manifest
        self.name = manifest["name"]
        self.label = manifest["label"]
        self.version = manifest["version"]

    def register_routes(self, app) -> None:
        """
        Registra os Blueprints (web/API) do módulo. Default (skill 09):
        auto-descoberta via pkgutil, escopada à pasta deste módulo
        (controller/ e api/routes/) — sobrescrever só quando o módulo
        precisar de ordem de registro específica ou quiser excluir
        algum Blueprint da descoberta automática.
        """
        from core.module_discovery import own_base_package, discover_blueprints

        info = own_base_package(self)
        if not info:
            return
        base_package, _ = info
        for blueprint in discover_blueprints(base_package):
            app.register_blueprint(blueprint)

    def get_transactions(self) -> list[dict]:
        """
        Transações navegáveis que este módulo expõe (skill 00, termo
        "Transação"). Default (skill 09): auto-gerado a partir dos
        models deste módulo (via register_models(), quando a subclasse
        tiver esse método — Plugin não tem, então continua vazio por
        padrão, igual sempre foi). Sobrescrever quando o módulo quiser
        ícone/grupo/ordem customizados em vez do automático.

        Cada item: {"code": "BRW_YEAST_BANK", "label": "Banco de
        Levedura", "route": "/brewstation/yeast-strains",
        "permission_required": "yeast_strains.list", "icon": "...",
        "group": "..."}. `permission_required` é opcional — None
        significa visível a qualquer usuário autenticado.
        """
        from core.module_discovery import auto_transactions_from_models

        register_models = getattr(self, "register_models", None)
        if not callable(register_models):
            return []
        return auto_transactions_from_models(register_models(), group_label=self.label)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} v{self.version}>"
