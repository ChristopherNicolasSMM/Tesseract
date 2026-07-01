"""
model/core/system_config.py

Tabela tesseract_system_config — chave/valor para parâmetros alteráveis
em runtime (skill 03, seção 5). Nunca usar para segredo — isso vai em
.env (ver core/config.py).
"""
from core.db import db


class SystemConfig(db.Model):
    __tablename__ = "tesseract_system_config"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(150), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    value_type = db.Column(db.String(20), default="string", nullable=False)

    @staticmethod
    def get(key: str, default=None):
        row = SystemConfig.query.filter_by(key=key).first()
        if row is None:
            return default
        return SystemConfig._cast(row.value, row.value_type)

    @staticmethod
    def _cast(value: str, value_type: str):
        if value is None:
            return None
        if value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        if value_type == "int":
            return int(value)
        if value_type == "json":
            import json
            return json.loads(value)
        return value

    def __repr__(self) -> str:
        return f"<SystemConfig {self.key}={self.value!r}>"
