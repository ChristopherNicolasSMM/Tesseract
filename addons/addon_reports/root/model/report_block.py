"""Blocos compartilhados como snapshots; inserções não mantêm vínculos vivos."""
from annotations import label, plural, display_field
from core.db import db
from .report_template import utcnow


@label('Bloco de relatório')
@plural('report_blocks')
@display_field('name')
class ReportBlock(db.Model):
    __tablename__ = 'report_block'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    node_json = db.Column(db.JSON, nullable=False)
    source_json = db.Column(db.JSON, nullable=False)
    content_hash = db.Column(db.String(64), nullable=False)
    lock_version = db.Column(db.Integer, nullable=False, default=1)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('tesseract_user.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    deleted_at = db.Column(db.DateTime)

    def to_dict(self):
        return {key:getattr(self,key) for key in ('id','key','name','content_hash','lock_version')}
