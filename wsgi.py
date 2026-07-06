"""
Ponto de entrada da aplicação.

Uso local:
    flask --app wsgi run --debug

Uso em produção (gunicorn, etc.):
    gunicorn wsgi:app
"""
from dotenv import load_dotenv as _load_dotenv
_load_dotenv()

from core.app_factory import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
