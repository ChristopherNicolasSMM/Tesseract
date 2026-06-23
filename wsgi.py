"""
Ponto de entrada da aplicação.

Uso local:
    flask --app wsgi run --debug

Uso em produção (gunicorn, etc.):
    gunicorn wsgi:app
"""
from core.app_factory import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
