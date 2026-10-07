"""Responsáveis administrativos, sem atribuir acesso RBAC automaticamente."""
from annotations import label, plural, display_field, field_labels
from core.db import db


@label('Responsável da organização')
@plural('organization_contacts')
@display_field('name')
@field_labels({'name': 'Nome', 'role': 'Função', 'cpf': 'CPF', 'email': 'E-mail', 'phone': 'Telefone', 'is_active': 'Ativo'})
class OrganizationContact(db.Model):
    __tablename__ = 'tesseract_organization_contact'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('tesseract_organization.id', ondelete='RESTRICT'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(80), nullable=False)
    cpf = db.Column(db.String(11), nullable=True)
    email = db.Column(db.String(254), nullable=True)
    phone = db.Column(db.String(16), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())

    def to_dict(self):
        return {field: getattr(self, field) for field in ('id', 'organization_id', 'name', 'role', 'cpf', 'email', 'phone', 'is_active')}
