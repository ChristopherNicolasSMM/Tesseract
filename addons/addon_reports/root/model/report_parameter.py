"""Parâmetros tipados por revisão; não armazenam valores das emissões."""
from annotations import label, plural
from core.db import db
from .report_template import utcnow
from .report_template_version import ReportTemplateVersion


@label('Parâmetro de relatório')
@plural('report_parameters')
class ReportParameter(db.Model):
    __tablename__ = 'report_parameter'
    __table_args__ = (db.UniqueConstraint('version_id', 'key', name='uq_reports_parameter'),)
    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey(ReportTemplateVersion.id), nullable=False)
    key = db.Column(db.String(80), nullable=False)
    label = db.Column(db.String(120), nullable=False)
    schema_json = db.Column(db.JSON, nullable=False)
    is_required = db.Column(db.Boolean, nullable=False, default=False)
    has_default = db.Column(db.Boolean, nullable=False, default=False)
    default_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        result = {'key': self.key, 'label': self.label, 'schema': self.schema_json,
                  'required': self.is_required}
        if self.has_default:
            result['default'] = self.default_json
        return result
