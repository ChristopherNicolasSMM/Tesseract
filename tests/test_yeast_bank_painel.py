"""
tests/test_yeast_bank_painel.py

Painel integrado do Yeast Bank (skill 21) — /brewstation/yeast-bank/painel.
Página escrita à mão (skill 17/18), dado consumido via API REST já
coberta noutros testes; aqui cobre a casca (rota, login, JS servido,
config presente) e o shape de dado que o JS depende (container/
device aninhados, alertas, bank_item aninhado no evento).

Interação real de clique-em-linha-popula-outra-grid não é testável
via pytest (sem navegador neste ambiente) — validado manualmente via
requisições HTTP diretas simulando o que o JS faz (ver os testes de
shape abaixo), mas a interação em si só é confirmada abrindo a tela.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _login_admin(app, client):
    with app.app_context():
        admin = User(
            username="admin", email="admin@test.local",
            nome="Admin", nome_completo="Administrador", celular="11999999999",
            is_admin=True, is_active=True,
        )
        admin.set_password("senha123")
        db.session.add(admin)
        db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "senha123"})


def test_painel_exige_login(client):
    resp = client.get("/brewstation/yeast-bank/painel")
    assert resp.status_code in (302, 401)


def test_painel_renderiza_logado(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/yeast-bank/painel")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "aba-cepas" in html
    assert "aba-eventos" in html
    assert 'id="painel-config"' in html


def test_painel_tem_atalhos_pras_telas_crudgen(app, client):
    _login_admin(app, client)
    html = client.get("/brewstation/yeast-bank/painel").get_data(as_text=True)
    assert "/brewstation/yeast-storage-devices/" in html
    assert "/brewstation/yeast-bank-configs/" in html


def test_painel_js_files_sao_servidos(app, client):
    _login_admin(app, client)
    for path in [
        "/static/js/yeast_bank_painel/yeast_bank_painel-tesseract-data.js",
        "/static/js/yeast_bank_painel/painel-cepas.js",
        "/static/js/yeast_bank_painel/painel-eventos.js",
    ]:
        resp = client.get(path)
        assert resp.status_code == 200, path


def test_painel_html_nao_tem_script_inline_alem_do_config():
    # Mesma regra da skill 18 (test_full_nao_tem_javascript_inline) —
    # só o bloco de config (application/json) e os <script src="…">.
    with open(
        "addons/addon_brewstation/features/feature_yeast_bank/templates/feature_yeast_bank/painel.html",
        encoding="utf-8",
    ) as f:
        html = f.read()
    import re
    scripts = re.findall(r"<script(?![^>]*type=\"application/json\")[^>]*>(.*?)</script>", html, re.DOTALL)
    for conteudo in scripts:
        assert conteudo.strip() == "", "Encontrado JavaScript inline no painel.html"


# ── Shape de dado que o JS depende (skill 21) ───────────────────────────────

def _make_scenario(app, client):
    r = client.post("/api/brewstation/yeast-strains/", json={"name": "US-05"})
    strain_id = r.get_json()["item"]["id"]
    r = client.post("/api/brewstation/yeast-storage-devices/", json={"name": "Freezer X"})
    device_id = r.get_json()["item"]["id"]
    r = client.post(
        "/api/brewstation/yeast-containers/",
        json={"name": "Caixa 1", "device_id": device_id},
    )
    container_id = r.get_json()["item"]["id"]
    r = client.post(
        "/api/brewstation/yeast-bank-items/",
        json={"strain_id": strain_id, "storage_type": "slant", "container_id": container_id},
    )
    item_id = r.get_json()["item"]["id"]
    return strain_id, item_id


def test_item_do_banco_traz_container_e_dispositivo_aninhados(app, client):
    # painel-cepas.js lê item.container.name e item.container.device.name
    # direto do JSON, sem requisição extra por linha.
    _login_admin(app, client)
    _, item_id = _make_scenario(app, client)

    r = client.get(f"/api/brewstation/yeast-bank-items/{item_id}")
    item = r.get_json()["item"]
    assert item["container"]["name"] == "Caixa 1"
    assert item["container"]["device"]["name"] == "Freezer X"


def test_item_do_banco_traz_sinalizadores_de_alerta(app, client):
    # painel-cepas.js usa item.expiry_alert/low_viability_alert pra
    # destacar a linha (skill 21, reanálise de eventos).
    _login_admin(app, client)
    r = client.get(
        f"/api/brewstation/yeast-bank-items/"
        f"{_make_scenario(app, client)[1]}"
    )
    item = r.get_json()["item"]
    assert "expiry_alert" in item
    assert "low_viability_alert" in item


def test_evento_traz_bank_item_com_strain_aninhado(app, client):
    # painel-eventos.js lê evento.bank_item.strain.name pra derivar a
    # cepa (removida do próprio evento na skill 21).
    _login_admin(app, client)
    _, item_id = _make_scenario(app, client)

    r = client.post(
        "/api/brewstation/yeast-bank-events/",
        json={"bank_item_id": item_id, "event_type": "Outro"},
    )
    r2 = client.get(f"/api/brewstation/yeast-bank-events/{r.get_json()['item']['id']}")
    event = r2.get_json()["item"]
    assert event["bank_item"]["strain"]["name"] == "US-05"
