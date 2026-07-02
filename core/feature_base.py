"""
core/feature_base.py

Feature não tem ciclo de ativação próprio no ModuleManager — ela vive
e morre com o Addon pai (skill 00: "não existe fora de um Addon").
Por isso não herda de ModuleBase; é instanciada e registrada PELO
AddonBase.get_features() que a contém.
"""
from abc import ABC


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

    def register_models(self) -> list:
        """
        Default (skill 09): auto-descoberta via pkgutil, escopada à
        pasta model/ desta Feature — sobrescrever só quando precisar
        de ordem específica ou quiser excluir algum model.
        """
        from core.module_discovery import own_base_package, discover_models

        info = own_base_package(self)
        if not info:
            return []
        base_package, _ = info
        return discover_models(base_package)

    def register_routes(self, app) -> None:
        """
        Registra os Blueprints (web/API) da Feature. Default (skill
        09): auto-descoberta via pkgutil, escopada a controller/ e
        api/routes/ desta Feature — sem rota própria (Feature que só
        contribui tabela/dado consumido por outra parte do Addon), a
        descoberta simplesmente não encontra nada, igual o `pass`
        manual que já existia.
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
        Ver ModuleBase.get_transactions() — mesmo contrato e mesmo
        default de auto-geração a partir dos models desta Feature
        (skill 09).
        """
        from core.module_discovery import auto_transactions_from_models

        return auto_transactions_from_models(self.register_models(), module_name=self.name, module_label=self.label)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} v{self.version}>"
