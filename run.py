#!/usr/bin/env python3
"""
run.py

Ponto de entrada único do Tesseract. Não exige o executável `flask`
instalado globalmente — basta `pip install -r requirements.txt`
(Flask já vem como biblioteca Python, é só o *comando* `flask` que
pode não estar no PATH fora de um venv ativado).

Usa flask.cli.FlaskGroup por baixo, então TODOS os comandos já
registrados em core/cli.py (`init-admin`, `generate`) funcionam aqui
automaticamente, sem duplicar nenhuma lógica — e ganham de graça os
comandos padrão do Flask (`shell`, `routes`).

Uso:
    python run.py start                          # inicia o servidor
    python run.py start --port 8000 --debug
    python run.py init-admin --username admin --password admin123
    python run.py generate --model caminho.py --addon brewstation
    python run.py routes                          # lista todas as rotas (built-in Flask)
    python run.py --help                          # lista todos os comandos
"""
import click
from flask.cli import FlaskGroup

from core.app_factory import create_app

cli = FlaskGroup(
    create_app=create_app,
    help="Tesseract — comandos de desenvolvimento e administração.",
)


@cli.command("start")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=5000, type=int, show_default=True)
@click.option(
    "--debug/--no-debug", default=None,
    help="Por padrão, segue o LOG_LEVEL/DEBUG da config do ambiente (TESSERACT_ENV).",
)
def start(host, port, debug):
    """Inicia o servidor de desenvolvimento (equivalente a `flask run`)."""
    app = create_app()
    if debug is None:
        debug = bool(app.config.get("DEBUG", True))#Padrão ativo
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    start()
