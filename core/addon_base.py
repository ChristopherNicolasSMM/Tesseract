"""
core/addon_base.py

Todo Addon cria tabela(s) — por isso exige table_prefix e register_models().
Ver skill 00 (definição) e skill 02 (regra tri-nível de prefixo).
"""
from abc import abstractmethod

from core.module_base import ModuleBase


class AddonBase(ModuleBase):
    module_type = "addon"

    def __init__(self, manifest: dict):
        super().__init__(manifest)
        table_prefix = manifest.get("table_prefix")
        if not table_prefix:
            raise ValueError(
                f"Addon {self.name!r}: 'table_prefix' é obrigatório no "
                f"addon.json (skill 02 e skill 03)."
            )
        self.table_prefix = table_prefix

    @abstractmethod
    def register_models(self) -> list:
        """
        Retorna a lista de classes de model deste Addon (núcleo, sem
        Feature). O ModuleManager aplica o prefixo completo e agrega ao
        MetaData compartilhado — nunca o próprio Addon chama
        db.create_all().
        """
        raise NotImplementedError

    def get_features(self) -> list:
        """
        Retorna as Features ativas deste Addon (instâncias de
        FeatureBase). Vazio por padrão — Addons sem Feature não
        precisam sobrescrever.
        """
        return []
