"""
model/core/message_queue.py

Fila de mensagens assíncronas (email, webhook, notification) com
retry. Portado do PyTeca (model/core/admin/message_queue.py) — vem
junto com o sistema de tasks (TaskService.process_queue() depende
dele), não é objetivo isolado desta fase.
"""
from datetime import datetime, timezone

from core.db import db


class MessageQueue(db.Model):
    __tablename__ = "tesseract_message_queue"

    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(50), nullable=False)     # email, webhook, notification
    payload = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), default="pending")   # pending, processing, done, failed, cancelled
    retries = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    scheduled_for = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = db.Column(db.DateTime, nullable=True)
    error_msg = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<MessageQueue id={self.id} channel={self.channel}>"
