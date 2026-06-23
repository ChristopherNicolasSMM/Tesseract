"""
core/feature_base.py

Feature não tem ciclo de ativação próprio no ModuleManager — ela vive
e morre com o Addon pai (skill 00: "não existe fora de um Addon").
Por isso não herda de ModuleBase; é instanciada e registrada PELO
AddonBase.get_features() que a contém.
"""
from abc import ABC, abstractmethod


class FeatureBase(ABC):
    def __init__(self, manifest: dict, addon_table_prefix: str):
        self.manifest = manifest
        self.name = manifest["name"]
        self.label = manifest["label"]
        self.version = manifest["version"]

        suffix = manifest.get("table_prefix_suffix")
        if not suffix:
            raise ValueError(
                f"Feature {self.name!r}: 'table_prefix_suffix' é "
                f"obrigatório no feature.json (skill 02/03)."
            )
        self.table_prefix_suffix = suffix
        self.table_prefix = f"{addon_table_prefix}_{suffix}"

    @abstractmethod
    def register_models(self) -> list:
        raise NotImplementedError

    def register_routes(self, app) -> None:
        """
        Registra os Blueprints (web/API) da Feature. Default no-op —
        nem toda Feature precisa de rota própria (pode só contribuir
        com tabela/dados consumidos por outra parte do Addon).
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} v{self.version}>"
