"""
model/core/scheduled_task.py

Tarefa agendável/executável sob demanda. Portado do PyTeca
(model/core/admin/scheduled_task.py) quase 1:1 — ver
docs/skills/05-proposta-addon-device-manager-e-mqtt.md (decisão de
2026-06-29: portar sistema de tasks como infraestrutura geral do
Core, antes da Fase E do device_manager).
"""
from datetime import datetime, timezone

from core.db import db


class ScheduledTask(db.Model):
    __tablename__ = "tesseract_scheduled_task"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    task_type = db.Column(db.String(50), nullable=False)   # python_call, http_request, sql
    target = db.Column(db.Text, nullable=False)            # função registrada, URL, ou SQL
    schedule = db.Column(db.String(100), nullable=False)   # cron string ou intervalo em minutos
    status = db.Column(db.String(20), default="active")    # active, paused, completed, pending_approval, rejected
    last_run = db.Column(db.DateTime, nullable=True)
    next_run = db.Column(db.DateTime, nullable=True)
    result = db.Column(db.Text, nullable=True)
    requires_approval = db.Column(db.Boolean, default=False)
    approved = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<ScheduledTask {self.name}>"
