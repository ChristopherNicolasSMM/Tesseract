"""Identidade compartilhada de modelos; organização não define tenant."""
from datetime import datetime, timezone
from annotations import label, plural, display_field, permission, menu_icon
from core.db import db


def utcnow():
    return datetime.now(timezone.utc)


@label('Modelo de relatório')
@plural('report_templates')
@display_field('name')
@menu_icon('bi-file-earmark-text')
@permission('publish', description='Publicar revisão de relatório')
@permission('render', description='Gerar relatório')
class ReportTemplate(db.Model):
    __tablename__ = 'report_template'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    active_version_number = db.Column(db.Integer, nullable=True)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('tesseract_user.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {'id': self.id, 'key': self.key, 'name': self.name,
                'active_version': self.active_version_number, 'is_deleted': self.is_deleted}
