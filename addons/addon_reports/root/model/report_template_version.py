"""Revisão com concorrência otimista e conteúdo declarativo."""
from annotations import label, plural
from core.db import db
from .report_template import ReportTemplate, utcnow


@label('Revisão de relatório')
@plural('report_template_versions')
class ReportTemplateVersion(db.Model):
    __tablename__ = 'report_template_version'
    __table_args__ = (db.UniqueConstraint('template_id', 'version_number', name='uq_reports_revision'),
                      db.CheckConstraint("status IN ('draft', 'published')", name='ck_reports_revision_status'))
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey(ReportTemplate.id), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='draft')
    lock_version = db.Column(db.Integer, nullable=False, default=1)
    layout_json = db.Column(db.JSON, nullable=False)
    data_schema_json = db.Column(db.JSON, nullable=False)
    sample_data_json = db.Column(db.JSON, nullable=False)
    content_hash = db.Column(db.String(64))
    published_at = db.Column(db.DateTime)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('tesseract_user.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {'id': self.id, 'template_id': self.template_id, 'version': self.version_number,
                'status': self.status, 'lock_version': self.lock_version,
                'layout': self.layout_json, 'data_schema': self.data_schema_json,
                'sample_data': self.sample_data_json, 'content_hash': self.content_hash}
