"""
core/cli.py

Comandos Flask CLI do Core. `init-admin` resolve o problema do "ovo e
da galinha": toda a API de usuários é admin-only, então o primeiro
admin precisa nascer por fora da API.

Uso:
    flask --app wsgi init-admin --username admin --password admin123
"""
import click
from flask.cli import with_appcontext


def register_cli_commands(app) -> None:
    @app.cli.command("init-admin")
    @click.option("--username", default="admin", show_default=True)
    @click.option("--email", default="admin@tesseract.local", show_default=True)
    @click.option("--password", default="admin123", show_default=True)
    @click.option("--nome", default="Admin", show_default=True)
    @click.option("--nome-completo", default="Administrador", show_default=True)
    @click.option("--celular", default="00000000000", show_default=True)
    @with_appcontext
    def init_admin(username, email, password, nome, nome_completo, celular):
        from core.db import db
        from model.core.user import User

        existing = User.query.filter_by(username=username).first()
        if existing:
            click.echo(f"Usuário '{username}' já existe.")
            return

        admin = User(
            username=username,
            email=email,
            nome=nome,
            nome_completo=nome_completo,
            celular=celular,
            is_admin=True,
            is_active=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Usuário admin '{username}' criado com sucesso.")
