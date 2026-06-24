"""
addons/addon_brewstation/features/feature_device_manager/model/device_function.py

Funções que podem ser atribuídas a portas de devices (sensor,
atuador, híbrido). Pré-definidas (sistema) ou customizadas pelo
usuário. Sem FK — é a tabela "raiz" desta Feature.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length


@label("Função de Dispositivo")
@plural("device_functions")
@required("name", message="Nome interno da função é obrigatório")
@required("category", message="Categoria é obrigatória (sensor/actuator/hybrid)")
@max_length("name", 100)
class DeviceFunction(db.Model):
    __tablename__ = "function"  # nome curto — CrudGen/ModuleManager aplicam o prefixo

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), unique=True, nullable=False)
    display_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=False)  # sensor, actuator, hybrid
    unit = db.Column(db.String(20), nullable=True)  # °C, %, V, bar...
    data_type = db.Column(db.String(20), nullable=False, default="float")  # float, int, bool, string
    min_value = db.Column(db.Float, nullable=True)
    max_value = db.Column(db.Float, nullable=True)
    is_predefined = db.Column(db.Boolean, default=False, nullable=False)
    icon = db.Column(db.String(50), nullable=True)  # classe de ícone Bootstrap

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "unit": self.unit,
            "data_type": self.data_type,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "is_predefined": self.is_predefined,
            "icon": self.icon,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<DeviceFunction {self.name} ({self.category})>"
