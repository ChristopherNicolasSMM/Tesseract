"""
core/plugin_base.py

Plugin nunca cria tabela — por definição (skill 00). register_models()
não existe aqui de propósito: se uma subclasse de PluginBase tentar
declarar isso, é erro de classificação do módulo (deveria ser Addon).
"""
from core.module_base import ModuleBase


class PluginBase(ModuleBase):
    module_type = "plugin"

    def __init__(self, manifest: dict):
        if "table_prefix" in manifest:
            raise ValueError(
                f"Plugin {manifest.get('name')!r}: campo 'table_prefix' "
                f"é proibido em plugin.json (skill 03). Se este módulo "
                f"precisa de tabela, ele deveria ser um Addon."
            )
        super().__init__(manifest)
