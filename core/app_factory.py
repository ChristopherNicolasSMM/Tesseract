"""
core/app_factory.py

Fase 0 — Scaffold mínimo.
Responsabilidade única nesta fase: confirmar que o Core sobe sozinho,
sem nenhum Addon/Plugin carregado ainda.

Nas próximas fases, create_app() vai:
- inicializar o DB factory (Fase 1)
- inicializar o ModuleManager e descobrir Addons/Plugins (Fase 1)
- registrar o EventBus (Fase 1)
- registrar RBAC/login (Fase 2)
"""
from flask import Flask, jsonify


def create_app(config_object: str | None = None) -> Flask:
    app = Flask(__name__)

    if config_object:
        app.config.from_object(config_object)

    @app.route("/health")
    def health():
        return jsonify(
            status="ok",
            project="Tesseract",
            phase=0,
            message="Core no ar. Nenhum Addon/Plugin carregado ainda.",
        )

    return app
