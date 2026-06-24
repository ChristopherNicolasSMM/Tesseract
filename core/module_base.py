"""
core/module_base.py

Classe abstrata comum a Addon e Plugin (skill 00, termo "Module").
Nenhum Addon/Plugin herda diretamente daqui — sempre via AddonBase ou
PluginBase, que impõem a regra de tabela (skill 00/02).
"""
from abc import ABC, abstractmethod


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

    @abstractmethod
    def register_routes(self, app) -> None:
        """Registra os Blueprints (web/API) do módulo."""
        raise NotImplementedError

    def get_transactions(self) -> list[dict]:
        """
        Transações navegáveis que este módulo expõe (skill 00, termo
        "Transação"). Vazio por padrão — sobrescrever quando o módulo
        tiver pontos de entrada para o launcher/menu.

        Cada item: {"code": "BRW_YEAST_BANK", "label": "Banco de
        Levedura", "route": "/brewstation/yeast-strains",
        "permission_required": "yeast_strains.list", "icon": "...",
        "group": "..."}. `permission_required` é opcional — None
        significa visível a qualquer usuário autenticado.
        """
        return []

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} v{self.version}>"
