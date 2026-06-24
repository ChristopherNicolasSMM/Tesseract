"""
core/db.py

DB factory único, compartilhado por Core, Addons e Features.
SQLite em dev, Postgres em produção — a troca é só pela
SQLALCHEMY_DATABASE_URI vinda de core/config.py, nenhum código aqui
sabe (nem deveria saber) qual banco está por baixo.

Nenhum Addon/Feature/Plugin importa SQLAlchemy diretamente — todos
importam `db` deste módulo, igual ao padrão já usado em
PyTeca/BrewStation.

`migrate` (Flask-Migrate/Alembic) cobre ALTER de tabela já existente
(ex.: adicionar coluna a um model que já tinha tabela criada) — caso
real que `db.create_all()` nunca resolve, porque ele só cria tabela
que não existe, nunca altera uma que já existe. Ver BACKLOG.md.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def init_db(app) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
