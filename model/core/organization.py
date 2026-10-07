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

    legal_name = db.Column(db.String(200), nullable=True)
    trade_name = db.Column(db.String(120), nullable=True)
    cnpj = db.Column(db.String(14), nullable=True, unique=True)
    state_registration = db.Column(db.String(40), nullable=True)
    municipal_registration = db.Column(db.String(40), nullable=True)
    email = db.Column(db.String(254), nullable=True)
    phone = db.Column(db.String(16), nullable=True)
    website = db.Column(db.String(250), nullable=True)
    cep = db.Column(db.String(8), nullable=True)
    logradouro = db.Column(db.String(200), nullable=True)
    numero = db.Column(db.String(20), nullable=True)
    complemento = db.Column(db.String(100), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    cidade = db.Column(db.String(100), nullable=True)
    estado = db.Column(db.String(2), nullable=True)
    pais = db.Column(db.String(60), nullable=True)
    contacts = db.relationship('OrganizationContact', lazy='select', order_by='OrganizationContact.id')

    def to_dict(self):
        return {'id': self.id, 'code': self.code, 'name': self.name, 'is_active': self.is_active,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
                **{name: getattr(self, name) for name in PROFILE_FIELDS},
                'contacts': [contact.to_dict() for contact in self.contacts]}

PROFILE_FIELDS = {'legal_name': 200, 'trade_name': 120, 'cnpj': 14, 'state_registration': 40, 'municipal_registration': 40, 'email': 254, 'phone': 16, 'website': 250, 'cep': 8, 'logradouro': 200, 'numero': 20, 'complemento': 100, 'bairro': 100, 'cidade': 100, 'estado': 2, 'pais': 60}
