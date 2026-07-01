"""
model/core/model_field_definition.py

tesseract_model_field_definition — campos de um ModelDefinition (skill
06). FK interna Core->Core (model_definition_id), sempre permitida
pela skill 02.
"""
from core.db import db


class ModelFieldType:
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TEXT = "text"
    FOREIGN_KEY = "foreign_key"

    ALL = (STRING, INTEGER, FLOAT, BOOLEAN, DATE, DATETIME, TEXT, FOREIGN_KEY)

    # Mapeamento direto para o tipo de coluna SQLAlchemy usado no
    # model.py.j2 (core/crudgen/templates/model.py.j2).
    SQLALCHEMY_COLUMN = {
        STRING: "db.String",
        INTEGER: "db.Integer",
        FLOAT: "db.Float",
        BOOLEAN: "db.Boolean",
        DATE: "db.Date",
        DATETIME: "db.DateTime",
        TEXT: "db.Text",
        FOREIGN_KEY: "db.Integer",
    }


class ModelFieldDefinition(db.Model):
    __tablename__ = "tesseract_model_field_definition"

    id = db.Column(db.Integer, primary_key=True)
    model_definition_id = db.Column(
        db.Integer, db.ForeignKey("tesseract_model_definition.id"), nullable=False
    )

    field_name = db.Column(db.String(100), nullable=False)  # snake_case
    field_type = db.Column(db.String(20), nullable=False, default=ModelFieldType.STRING)

    nullable = db.Column(db.Boolean, nullable=False, default=True)
    unique = db.Column(db.Boolean, nullable=False, default=False)
    is_required = db.Column(db.Boolean, nullable=False, default=False)
    default_value = db.Column(db.String(255), nullable=True)
    max_length = db.Column(db.Integer, nullable=True)  # só para field_type=string

    # Validado em runtime pelo service (skill 06 §3.2): só aceita tabela
    # do mesmo Addon do ModelDefinition pai, ou "tesseract_user".
    fk_target_table = db.Column(db.String(150), nullable=True)

    label_text = db.Column(db.String(200), nullable=False)  # PT-BR, vira translation_key na geração

    is_listview_column = db.Column(db.Boolean, nullable=False, default=True)
    is_form_field = db.Column(db.Boolean, nullable=False, default=True)
    order_index = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "model_definition_id": self.model_definition_id,
            "field_name": self.field_name,
            "field_type": self.field_type,
            "nullable": self.nullable,
            "unique": self.unique,
            "is_required": self.is_required,
            "default_value": self.default_value,
            "max_length": self.max_length,
            "fk_target_table": self.fk_target_table,
            "label_text": self.label_text,
            "is_listview_column": self.is_listview_column,
            "is_form_field": self.is_form_field,
            "order_index": self.order_index,
        }

    def __repr__(self) -> str:
        return f"<ModelFieldDefinition {self.field_name}:{self.field_type}>"
