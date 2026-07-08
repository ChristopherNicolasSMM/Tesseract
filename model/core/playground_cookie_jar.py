"""
model/core/playground_cookie_jar.py

tesseract_playground_cookie_jar — sessão/cookies persistidos por
usuário do API/SQL Playground (skill 06, adenda "Playground v2",
§8.1). Escopo global por usuário (não por pasta/coleção — decisão
registrada na skill). Core, não passa pelo CrudGen.
"""
from datetime import datetime, timezone

from core.db import db


class PlaygroundCookieJar(db.Model):
    __tablename__ = "tesseract_playground_cookie_jar"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=False, unique=True)
    cookies_json = db.Column(db.JSON, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<PlaygroundCookieJar user_id={self.user_id}>"
