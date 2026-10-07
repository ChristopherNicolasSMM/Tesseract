"""Identidade compartilhada; não representa tenant, moeda ou saldo."""
from datetime import datetime, timezone
from annotations import label, plural, display_field, field_labels
from core.db import db


@label('Organização')
@plural('organizations')
@display_field('name')
@field_labels({'code': 'Código', 'name': 'Nome', 'is_active': 'Ativa'})
class Organization(db.Model):
    __tablename__ = 'tesseract_organization'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {'id': self.id, 'code': self.code, 'name': self.name, 'is_active': self.is_active,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None}
