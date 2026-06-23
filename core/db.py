"""
core/db.py

DB factory único, compartilhado por Core, Addons e Features.
SQLite em dev, Postgres em produção — a troca é só pela
SQLALCHEMY_DATABASE_URI vinda de core/config.py, nenhum código aqui
sabe (nem deveria saber) qual banco está por baixo.

Nenhum Addon/Feature/Plugin importa SQLAlchemy diretamente — todos
importam `db` deste módulo, igual ao padrão já usado em
PyTeca/BrewStation.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app) -> None:
    db.init_app(app)
