"""
model/core/associations.py

Tabelas de associação m:n entre User<->Role e Role<->Permission.
Não são tabelas "de negócio" — não passam pelo prefixo tri-nível da
skill 02 com nome de entidade próprio porque são puramente estruturais
do Core (mesmo padrão usado no PyTeca: user_roles, role_permissions).
"""
from core.db import db

user_roles = db.Table(
    "tesseract_user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("tesseract_user.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("tesseract_role.id"), primary_key=True),
)

role_permissions = db.Table(
    "tesseract_role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("tesseract_role.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("tesseract_permission.id"), primary_key=True),
)
