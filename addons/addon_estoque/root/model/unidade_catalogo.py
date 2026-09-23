"""Códigos de unidade; conteúdo das embalagens é definido por material."""
from core.db import db
from annotations import label, plural, display_field


@label("Unidade de medida")
@plural("unidades_catalogo")
@display_field("codigo")
class UnidadeCatalogo(db.Model):
    __tablename__ = "tesseract_estoque_unidade_catalogo"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    descricao = db.Column(db.String(100), nullable=False)
    dimensao = db.Column(db.String(20), nullable=False)
    fator_referencia = db.Column(db.Float, nullable=True)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self):
        return {"id": self.id, "codigo": self.codigo, "descricao": self.descricao,
                "dimensao": self.dimensao, "fator_referencia": self.fator_referencia,
                "is_deleted": self.is_deleted}
