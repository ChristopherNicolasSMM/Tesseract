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

    @app.cli.command("generate")
    @click.option("--model", "model_path", required=True, help="Caminho do arquivo .py com o model anotado")
    @click.option("--class-name", default=None, help="Nome da classe, se o arquivo tiver mais de um model")
    @click.option("--addon", required=True)
    @click.option("--feature", default=None)
    @click.option("--overwrite", is_flag=True, default=False)
    @with_appcontext
    def generate_cmd(model_path, class_name, addon, feature, overwrite):
        from pathlib import Path
        import importlib.util
        import inspect

        from core.db import db
        from core.crudgen.generator import generate

        full_path = Path(model_path).resolve()
        # app.root_path resolve para a pasta core/ (onde Flask(__name__) foi
        # instanciado em core/app_factory.py) — a raiz do projeto é o pai dela.
        project_root = Path(app.root_path).parent.resolve()

        spec = importlib.util.spec_from_file_location(full_path.stem, full_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        candidates = [
            obj for _, obj in inspect.getmembers(module, inspect.isclass)
            if hasattr(obj, "__tablename__") and obj.__module__ == module.__name__
        ]
        if class_name:
            candidates = [c for c in candidates if c.__name__ == class_name]

        if not candidates:
            click.echo("Nenhum model encontrado no arquivo (precisa ter __tablename__).")
            return
        if len(candidates) > 1:
            click.echo(f"Mais de um model encontrado: {[c.__name__ for c in candidates]}. Use --class-name.")
            return

        model_class = candidates[0]
        result = generate(
            model_class,
            project_root=project_root,
            addon=addon,
            feature=feature,
            overwrite=overwrite,
        )
        click.echo(f"Tabela: {result['table_name']}")
        click.echo(f"Arquivos escritos: {len(result['written'])}")
        click.echo(f"Arquivos existentes preservados: {len(result['skipped_existing'])}")
        click.echo(f"Hooks preservados: {len(result['skipped_hooks'])}")
        click.echo(f"Permissões novas: {result['permissions']['created']}")
