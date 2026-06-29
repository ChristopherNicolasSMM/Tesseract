"""
model/core/task_log.py

Histórico de execuções de ScheduledTask. Portado do PyTeca
(model/core/admin/task_log.py) quase 1:1.
"""
from datetime import datetime, timezone

from core.db import db


class TaskLog(db.Model):
    __tablename__ = "tesseract_task_log"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tesseract_scheduled_task.id"), nullable=True)
    task_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)     # running, success, failure
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = db.Column(db.DateTime, nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)
    result = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)

    def __repr__(self) -> str:
        return f"<TaskLog {self.task_name} {self.status}>"
