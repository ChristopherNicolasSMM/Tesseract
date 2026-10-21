"""
addons/addon_brewstation/features/feature_device_manager/model/device_function.py

Funções que podem ser atribuídas a portas de devices (sensor,
atuador, híbrido). Pré-definidas (sistema) ou customizadas pelo
usuário. Sem FK — é a tabela "raiz" desta Feature.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length, display_field, enum_field, field_labels
from sqlalchemy import event, inspect
from .device_function_options import CATEGORY_OPTIONS, DATA_TYPE_OPTIONS, canonical_category


@label("Função de Dispositivo")
@plural("device_functions")
@enum_field('category', options=CATEGORY_OPTIONS, label='Categoria')
@enum_field('data_type', options=DATA_TYPE_OPTIONS, label='Tipo de dado')
@field_labels({'category':'Categoria', 'data_type':'Tipo de dado'})
@display_field("display_name")
@required("name", message="Nome interno da função é obrigatório")
@required("category", message="Categoria é obrigatória (sensor/actuator/hybrid)")
@required('data_type', message='Tipo de dado é obrigatório')
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
            "category": canonical_category(self.category),
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


@event.listens_for(DeviceFunction, 'before_insert')
@event.listens_for(DeviceFunction, 'before_update')
def validate_fixed_options(mapper, connection, target):
    """Commit-time validation also covers generated services/API without editing them.

    Unrelated edits/deletion do not rewrite or block unknown legacy values.
    The form requires explicit correction when those fields are edited.
    """
    state = inspect(target)
    if state.pending or state.attrs.category.history.has_changes():
        value = canonical_category(target.category)
        if value not in dict(CATEGORY_OPTIONS):
            raise ValueError('Categoria inválida. Selecione Sensor, Atuador ou Híbrido.')
        target.category = value
    if state.pending or state.attrs.data_type.history.has_changes():
        value = 'float' if state.pending and target.data_type is None else target.data_type
        if value not in dict(DATA_TYPE_OPTIONS):
            raise ValueError('Tipo de dado inválido. Selecione uma opção da lista.')
        target.data_type = value
