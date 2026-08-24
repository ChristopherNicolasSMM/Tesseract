"""
tests/test_phase14_yeast_container.py

Cobre a entidade YeastContainer (skill 19 —
docs/skills/19-proposta-reestruturacao-yeast-bank-container.md): tabela
criada com o prefixo correto, Container sempre físico (device_id
obrigatório), YeastBankItem.container_id obrigatório (sem
storage_device_id direto) e listagem de itens filtrada por container.
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


def test_tabela_container_existe_com_prefixo_correto(app):
    with app.app_context():
        assert "tesseract_brewstation_yeastbank_container" in db.metadata.tables.keys()


def test_container_exige_device_id_sempre_fisico(app, client):
    _login_admin(app, client)

    # Sem device_id — Container é sempre físico (skill 19, decisão descartada:
    # container virtual). Deve falhar.
    r = client.post("/api/brewstation/yeast-containers/", json={"name": "Caixa órfã"})
    assert r.status_code != 201


def test_container_criado_e_vinculado_ao_device(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/yeast-storage-devices/", json={"name": "Freezer A"})
    device_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/yeast-containers/",
        json={"name": "Caixa 1", "container_type": "Caixa", "device_id": device_id},
    )
    assert r.status_code == 201
    data = r.get_json()["item"]
    assert data["device_id"] == device_id
    assert data["device"]["name"] == "Freezer A"


def test_bank_item_exige_container_id_nao_aceita_storage_device_id_direto(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/yeast-strains/", json={"name": "US-05"})
    strain_id = r.get_json()["item"]["id"]

    # Sem container_id — deve falhar (container_id é NOT NULL desde a
    # reestruturação da skill 19).
    r = client.post(
        "/api/brewstation/yeast-bank-items/",
        json={"strain_id": strain_id, "storage_type": "slant"},
    )
    assert r.status_code != 201


def test_listagem_de_itens_permite_filtrar_por_container(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/yeast-strains/", json={"name": "WLP001"})
    strain_id = r.get_json()["item"]["id"]

    r = client.post("/api/brewstation/yeast-storage-devices/", json={"name": "Geladeira 1"})
    device_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/yeast-containers/",
        json={"name": "Estante A", "container_type": "Estante", "device_id": device_id},
    )
    container_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/yeast-bank-items/",
        json={"strain_id": strain_id, "storage_type": "slant", "container_id": container_id},
    )
    assert r.status_code == 201
    item_id = r.get_json()["item"]["id"]

    r = client.get(f"/api/brewstation/yeast-bank-items/?container_id={container_id}")
    assert r.status_code == 200
    ids = [i["id"] for i in r.get_json()["items"]]
    assert item_id in ids


# ── Fase 15: preservação de dados do formulário em caso de erro ────────────
# Achado real (BACKLOG.md): antes desta fase, create()/update() faziam
# redirect() em qualquer erro de validação, descartando o formulário
# inteiro digitado. Cobertura via HTML (rota web, não API), que é onde
# o bug ocorria.

def test_create_via_html_com_erro_reabre_formulario_com_dados_digitados(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/yeast-strains/", json={"name": "US-05"})
    strain_id = r.get_json()["item"]["id"]
    r = client.post("/api/brewstation/yeast-storage-devices/", json={"name": "Freezer X"})
    device_id = r.get_json()["item"]["id"]
    r = client.post(
        "/api/brewstation/yeast-containers/",
        json={"name": "Caixa 1", "device_id": device_id},
    )
    container_id = r.get_json()["item"]["id"]

    # "0,5" num Float — vírgula em vez de ponto (o bug relatado)
    r = client.post(
        "/brewstation/yeast-bank-items/",
        data={
            "strain_id": str(strain_id), "storage_type": "Agar Inclinado",
            "container_id": str(container_id), "estimated_viability_pct": "0,5",
            "identification": "TESTE-PRESERVACAO",
        },
    )
    html = r.get_data(as_text=True)

    # Não é mais redirect (302) — reabre a própria tela (200) com o erro.
    assert r.status_code == 200
    assert "alert-danger" in html
    # O que a pessoa já tinha digitado continua no formulário.
    assert "TESTE-PRESERVACAO" in html
    assert 'value="0,5"' in html

    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import YeastBankItem
    with app.app_context():
        assert YeastBankItem.query.count() == 0  # nada foi salvo (correto)


# ── Fase 17/skill 20: introspecção de tipo SQLAlchemy → html_type ──────────

def _detail_html(client, item_id):
    r = client.get(f"/brewstation/yeast-bank-items/{item_id}")
    return r.get_data(as_text=True)


def _setup_item(app, client):
    _login_admin(app, client)
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
    return r.get_json()["item"]["id"]


def test_campo_date_vira_input_type_date(app, client):
    item_id = _setup_item(app, client)
    html = _detail_html(client, item_id)
    assert 'type="date" name="prepared_date"' in html
    assert 'type="date" name="expiry_date"' in html


def test_campo_datetime_vira_input_type_datetime_local(app, client):
    item_id = _setup_item(app, client)
    html = _detail_html(client, item_id)
    assert 'type="datetime-local" name="estimated_viability_updated_at"' in html


def test_campo_float_vira_input_type_number_com_step_any(app, client):
    item_id = _setup_item(app, client)
    html = _detail_html(client, item_id)
    assert 'type="number" name="estimated_viability_pct"' in html
    assert 'class="form-control crudgen-decimal-input"' in html
    assert 'step="any"' in html


def test_campo_text_vira_textarea(app, client):
    item_id = _setup_item(app, client)
    html = _detail_html(client, item_id)
    assert '<textarea name="viability_notes"' in html
    assert '<textarea name="discard_reason"' in html


def test_enum_field_continua_select_mesmo_com_introspeccao_de_tipo(app, client):
    # Precedência (skill 20, seção J): @enum_field sempre vence o tipo
    # da coluna, mesmo status sendo String (que sem @enum_field cairia
    # em text).
    item_id = _setup_item(app, client)
    html = _detail_html(client, item_id)
    assert '<select name="status"' in html
    assert 'type="text" name="status"' not in html


def test_weak_ref_continua_combo_mesmo_com_introspeccao_de_tipo(app, client):
    # Precedência (skill 20, seção J): @weak_ref sempre vence o tipo
    # da coluna, mesmo container_id sendo Integer (que sem @weak_ref
    # viraria number).
    item_id = _setup_item(app, client)
    html = _detail_html(client, item_id)
    assert 'class="weakref-combo-value"' in html
    assert 'type="number" name="container_id"' not in html


def test_script_de_normalizacao_decimal_incluido_na_pagina(app, client):
    item_id = _setup_item(app, client)
    html = _detail_html(client, item_id)
    assert "decimal_input_normalizer.js" in html


def test_checkbox_desmarcado_no_post_zera_campo_boolean(app, client):
    # Risco documentado na skill 20: HTML nunca manda o campo no POST
    # quando um checkbox está desmarcado — sem normalização, o valor
    # antigo persistiria mesmo a pessoa "desmarcando" na tela.
    # YeastStarterLog.contamination_detected é Boolean editável real.
    # Criação via API/web está bloqueada desde a skill 21 (Starter só
    # nasce via Evento do Banco) — cria direto no banco pra testar só
    # o update(), que não tem esse bloqueio.
    item_id = _setup_item(app, client)
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_starter_log import YeastStarterLog
        from core.db import db
        starter = YeastStarterLog(bank_item_id=item_id, contamination_detected=True)
        db.session.add(starter)
        db.session.commit()
        starter_id = starter.id
        assert starter.contamination_detected is True

    # POST via HTML sem "contamination_detected" no corpo — simula
    # checkbox desmarcado (o browser não manda a chave nesse caso).
    client.post(
        f"/brewstation/yeast-starter-logs/{starter_id}",
        data={"bank_item_id": str(item_id)},
    )
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_starter_log import YeastStarterLog
        starter = YeastStarterLog.query.get(starter_id)
        assert starter.contamination_detected is False


def test_update_via_html_com_erro_reabre_formulario_com_dados_digitados(app, client):
    _login_admin(app, client)

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

    r = client.post(
        f"/brewstation/yeast-bank-items/{item_id}",
        data={
            "strain_id": str(strain_id), "storage_type": "Agar Inclinado",
            "container_id": str(container_id), "estimated_viability_pct": "1,5",
            "identification": "EDITANDO-TESTE",
        },
    )
    html = r.get_data(as_text=True)

    assert r.status_code == 200
    assert "alert-danger" in html
    assert "EDITANDO-TESTE" in html
    assert 'value="1,5"' in html
