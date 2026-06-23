"""
model/core/user.py

tesseract_user — autenticação + perfil. Portado do PyTeca quase 1:1.

Decisão registrada (BACKLOG.md): a `RegistrationRequest` (fluxo de
auto-cadastro órfão herdado do BrewStation) NÃO foi portada agora —
hoje o único caminho de criação de usuário é admin-only
(/api/admin/users), via core/cli.py (`flask init-admin`) para o
primeiro usuário. Decidir depois se o auto-cadastro entra e como.
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from core.db import db


class User(UserMixin, db.Model):
    __tablename__ = "tesseract_user"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Identidade
    nome = db.Column(db.String(120), nullable=False)            # nickname
    nome_completo = db.Column(db.String(255), nullable=False)
    celular = db.Column(db.String(20), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=True)  # 000.000.000-00

    # Endereço (opcional, campos separados — skill 02, convenção de coluna)
    endereco_rua = db.Column(db.String(255), nullable=True)
    endereco_numero = db.Column(db.String(20), nullable=True)
    endereco_complemento = db.Column(db.String(120), nullable=True)
    endereco_bairro = db.Column(db.String(120), nullable=True)
    endereco_cidade = db.Column(db.String(120), nullable=True)
    endereco_uf = db.Column(db.String(2), nullable=True)
    endereco_cep = db.Column(db.String(10), nullable=True)

    # Perfil
    empresa = db.Column(db.String(255))
    cargo = db.Column(db.String(255))
    pais = db.Column(db.String(120))
    telefone = db.Column(db.String(50))
    foto_perfil = db.Column(db.String(255))  # caminho relativo em static/uploads

    roles = db.relationship(
        "Role", secondary="tesseract_user_roles", back_populates="users"
    )

    # ── Senha ────────────────────────────────────────────────────────────
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # ── CPF (validação no momento da atribuição, nunca silenciosa) ──────
    def set_cpf(self, cpf: str | None) -> None:
        from core.validators import format_cpf, validate_cpf

        if not cpf:
            self.cpf = None
            return
        if not validate_cpf(cpf):
            raise ValueError("CPF inválido.")
        self.cpf = format_cpf(cpf)

    @property
    def foto_url(self) -> str:
        if self.foto_perfil:
            return self.foto_perfil.replace("\\", "/")
        return "img/foto-padrao-perfil.png"

    @property
    def endereco_completo(self) -> str:
        if not self.endereco_rua:
            return "—"
        parts = [self.endereco_rua]
        if self.endereco_numero:
            parts.append(f"nº {self.endereco_numero}")
        if self.endereco_complemento:
            parts.append(self.endereco_complemento)
        line1 = ", ".join(parts)
        line2 = " - ".join(
            p for p in [self.endereco_bairro, self.endereco_cidade, self.endereco_uf] if p
        )
        cep = f"CEP {self.endereco_cep}" if self.endereco_cep else ""
        return " | ".join(p for p in [line1, line2, cep] if p)

    # ── Autorização — único ponto de decisão (skill 00) ─────────────────
    def has_permission(self, permission_name: str) -> bool:
        if self.is_admin:
            return True
        for role in self.roles:
            for perm in role.permissions:
                if perm.name == permission_name:
                    return True
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "nome": self.nome,
            "nome_completo": self.nome_completo,
            "celular": self.celular,
            "cpf": self.cpf,
            "endereco_rua": self.endereco_rua,
            "endereco_numero": self.endereco_numero,
            "endereco_complemento": self.endereco_complemento,
            "endereco_bairro": self.endereco_bairro,
            "endereco_cidade": self.endereco_cidade,
            "endereco_uf": self.endereco_uf,
            "endereco_cep": self.endereco_cep,
            "empresa": self.empresa,
            "cargo": self.cargo,
            "pais": self.pais,
            "telefone": self.telefone,
            "foto_perfil": self.foto_perfil,
        }

    def __repr__(self) -> str:
        return f"<User {self.username}>"
