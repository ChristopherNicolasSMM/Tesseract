"""
core/config_service.py

Camada fina sobre SystemConfig.get() (model/core/system_config.py).
Existe como módulo separado por dois motivos:
1. Import tardio fácil — quem precisa de config em runtime
   (core/versioning.py, futuros Addons) importa daqui, não do model
   diretamente, evitando dependência circular model <-> service.
2. Ponto único para, no futuro, adicionar cache em memória sem precisar
   mudar quem consome.
"""
from model.core.system_config import SystemConfig


class ConfigService:
    @staticmethod
    def get(key: str, default=None):
        return SystemConfig.get(key, default=default)
