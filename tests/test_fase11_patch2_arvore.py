"""
tests/test_fase11_patch2_arvore.py

Fase 11, Patch 2 — árvore de componentes do Designer
(parent_id/order_index), reparentar/reordenar, exclusão em cascata e
renderização aninhada (runtime + editor).
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.designer_page import DesignerPage
from model.core.designer_component import DesignerComponent


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


def _page(client, name="Página Árvore"):
    client.post("/admin/designer/", data={"name": name})
    with client.application.app_context():
        return DesignerPage.query.filter_by(name=name).first().id


def _add(client, page_id, comp_type, parent_id=None):
    payload = {"type": comp_type}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    resp = client.post(f"/admin/designer/{page_id}/components", json=payload)
    return resp


# ── schema ────────────────────────────────────────────────────────────

def test_componente_novo_nasce_na_raiz(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    comp = _add(client, page_id, "card").get_json()["component"]
    assert comp["parent_id"] is None
    assert comp["order_index"] == 0


def test_order_index_incrementa_entre_irmaos(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    a = _add(client, page_id, "label").get_json()["component"]
    b = _add(client, page_id, "label").get_json()["component"]
    assert a["order_index"] == 0
    assert b["order_index"] == 1


# ── criar dentro de contêiner ─────────────────────────────────────────

def test_cria_componente_dentro_de_container(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    card = _add(client, page_id, "card").get_json()["component"]
    filho = _add(client, page_id, "label", parent_id=card["id"]).get_json()["component"]
    assert filho["parent_id"] == card["id"]


def test_nao_cria_dentro_de_tipo_que_nao_aceita_filhos(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    botao = _add(client, page_id, "button").get_json()["component"]
    resp = _add(client, page_id, "label", parent_id=botao["id"])
    assert resp.status_code == 422


def test_nao_cria_com_pai_inexistente(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    resp = _add(client, page_id, "label", parent_id=999999)
    assert resp.status_code == 422


# ── reparentar / reordenar ────────────────────────────────────────────

def test_move_para_dentro_de_container(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    card = _add(client, page_id, "card").get_json()["component"]
    solto = _add(client, page_id, "label").get_json()["component"]

    resp = client.post(f"/admin/designer/component/{solto['id']}/move-to",
                       json={"parent_id": card["id"], "order_index": 0})
    assert resp.status_code == 200
    assert resp.get_json()["component"]["parent_id"] == card["id"]


def test_move_de_volta_para_raiz(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    card = _add(client, page_id, "card").get_json()["component"]
    filho = _add(client, page_id, "label", parent_id=card["id"]).get_json()["component"]

    client.post(f"/admin/designer/component/{filho['id']}/move-to",
                json={"parent_id": None, "order_index": 0})
    with app.app_context():
        assert DesignerComponent.query.get(filho["id"]).parent_id is None


def test_reordena_entre_irmaos(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    a = _add(client, page_id, "label").get_json()["component"]
    b = _add(client, page_id, "label").get_json()["component"]
    c = _add(client, page_id, "label").get_json()["component"]

    # move o terceiro pro começo
    client.post(f"/admin/designer/component/{c['id']}/move-to",
                json={"parent_id": None, "order_index": 0})

    with app.app_context():
        ordem = [x.id for x in DesignerComponent.query
                 .filter_by(page_id=page_id, parent_id=None)
                 .order_by(DesignerComponent.order_index).all()]
    assert ordem == [c["id"], a["id"], b["id"]]


def test_nao_move_para_dentro_de_si_mesmo(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    card = _add(client, page_id, "card").get_json()["component"]
    resp = client.post(f"/admin/designer/component/{card['id']}/move-to",
                       json={"parent_id": card["id"]})
    assert resp.status_code == 422


def test_nao_cria_ciclo_na_arvore(app, client):
    """A dentro de B dentro de A faria a renderização recursiva entrar
    em loop infinito."""
    _login_admin(app, client)
    page_id = _page(client)
    externo = _add(client, page_id, "card").get_json()["component"]
    interno = _add(client, page_id, "card", parent_id=externo["id"]).get_json()["component"]

    resp = client.post(f"/admin/designer/component/{externo['id']}/move-to",
                       json={"parent_id": interno["id"]})
    assert resp.status_code == 422


def test_nao_move_para_tipo_que_nao_aceita_filhos(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    botao = _add(client, page_id, "button").get_json()["component"]
    label = _add(client, page_id, "label").get_json()["component"]
    resp = client.post(f"/admin/designer/component/{label['id']}/move-to",
                       json={"parent_id": botao["id"]})
    assert resp.status_code == 422


def test_move_renumera_lista_de_origem(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    card = _add(client, page_id, "card").get_json()["component"]
    a = _add(client, page_id, "label").get_json()["component"]
    b = _add(client, page_id, "label").get_json()["component"]
    c = _add(client, page_id, "label").get_json()["component"]

    client.post(f"/admin/designer/component/{b['id']}/move-to",
                json={"parent_id": card["id"], "order_index": 0})

    with app.app_context():
        raiz = DesignerComponent.query.filter_by(page_id=page_id, parent_id=None) \
            .order_by(DesignerComponent.order_index).all()
        # sem buraco de índice depois da saída do b
        assert [x.order_index for x in raiz] == list(range(len(raiz)))


# ── exclusão em cascata ───────────────────────────────────────────────

def test_excluir_container_leva_filhos_junto(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    card = _add(client, page_id, "card").get_json()["component"]
    filho = _add(client, page_id, "label", parent_id=card["id"]).get_json()["component"]
    neto = _add(client, page_id, "badge", parent_id=card["id"]).get_json()["component"]

    resp = client.post(f"/admin/designer/component/{card['id']}/delete")
    deleted = resp.get_json()["deleted_ids"]
    assert set(deleted) == {card["id"], filho["id"], neto["id"]}

    with app.app_context():
        assert DesignerComponent.query.get(filho["id"]) is None
        assert DesignerComponent.query.get(neto["id"]) is None


# ── listagem ──────────────────────────────────────────────────────────

def test_endpoint_de_listagem_retorna_arvore_plana(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    card = _add(client, page_id, "card").get_json()["component"]
    _add(client, page_id, "label", parent_id=card["id"])

    resp = client.get(f"/admin/designer/{page_id}/components")
    assert resp.status_code == 200
    comps = resp.get_json()["components"]
    assert len(comps) == 2
    assert any(c["parent_id"] == card["id"] for c in comps)


# ── renderização ──────────────────────────────────────────────────────

def test_runtime_renderiza_filho_dentro_do_container(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    card = _add(client, page_id, "card").get_json()["component"]
    filho = _add(client, page_id, "label", parent_id=card["id"]).get_json()["component"]
    client.post(f"/admin/designer/component/{filho['id']}",
                json={"properties": {"text": "DENTRO DO CARD"}})

    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        db.session.commit()
        slug = page.slug

    resp = client.get(f"/designer/{slug}")
    body = resp.data.decode()
    assert "DENTRO DO CARD" in body
    assert "dsg-slot" in body
    # o filho aparece DEPOIS da abertura do card no HTML (está aninhado)
    assert body.index("dsg-slot") < body.index("DENTRO DO CARD")


def test_runtime_nao_duplica_filho_na_raiz(app, client):
    """Filho aninhado não pode ser renderizado também no topo do
    canvas — o laço de raiz filtra parent_id nulo."""
    _login_admin(app, client)
    page_id = _page(client)
    card = _add(client, page_id, "card").get_json()["component"]
    filho = _add(client, page_id, "label", parent_id=card["id"]).get_json()["component"]
    client.post(f"/admin/designer/component/{filho['id']}",
                json={"properties": {"text": "UNICO"}})

    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        db.session.commit()
        slug = page.slug

    body = client.get(f"/designer/{slug}").data.decode()
    assert body.count("UNICO") == 1


def test_editor_tem_painel_de_camadas(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    resp = client.get(f"/admin/designer/{page_id}/edit")
    assert b"layersPanel" in resp.data
    assert "Camadas".encode() in resp.data


def test_container_tem_props_de_layout(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    card = _add(client, page_id, "card").get_json()["component"]
    props = card["properties"]
    assert props["layout"] == "vertical"
    assert props["gap"] == 8
    assert props["padding"] == 12
    assert props["align"] == "stretch"


# ── Patch 2.1 — correções vistas no editor real ──────────────────────

def test_canvas_usa_variavel_do_style_dark_que_existe(app, client):
    """Achado real: static/css/themes.css nunca é carregado por nenhum
    template, então --bg-secondary/--border-color (usados no Patch 1.1)
    não existiam e o var() caía sempre no fallback claro."""
    _login_admin(app, client)
    page_id = _page(client)
    body = client.get(f"/admin/designer/{page_id}/edit").data.decode()
    assert "var(--dark-surface-2" in body
    assert "var(--bg-secondary" not in body
    assert "var(--border-color" not in body


def test_preview_de_container_tem_ponto_de_montagem_do_slot(app, client):
    """Achado real: o slot era anexado como irmão do preview; com
    h-100 no card/fieldset ele ficava fora da caixa visível e o drop
    pelo canvas era inalcançável."""
    _login_admin(app, client)
    page_id = _page(client)
    body = client.get(f"/admin/designer/{page_id}/edit").data.decode()
    assert "data-slot-mount" in body
    assert "querySelector('[data-slot-mount]')" in body


def test_alca_de_resize_e_recriada_apos_render(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    body = client.get(f"/admin/designer/{page_id}/edit").data.decode()
    assert "querySelector('.dsg-resize-handle')" in body


# ── Patch 2.2 — camadas vazias, drop no canvas, paletas colapsáveis ──

def test_adicionar_componente_atualiza_painel_de_camadas(app, client):
    """Achado real: renderLayers() só rodava no carregamento da página,
    então adicionar componente pela paleta deixava o painel de Camadas
    eternamente com 'Nenhum componente ainda'."""
    _login_admin(app, client)
    page_id = _page(client)
    body = client.get(f"/admin/designer/{page_id}/edit").data.decode()
    add_handler = body.split("data-add-type]")[1][:600]
    assert "renderLayers()" in add_handler


def test_reparentar_pelo_canvas_usa_mouseup_nao_drag_html5(app, client):
    """Achado real: o mousedown de attachDragResize chama
    preventDefault(), o que impede o dragstart do HTML5 de disparar —
    então dragSourceId ficava nulo e soltar dentro de um contêiner pelo
    canvas nunca funcionava. Trocado por detecção no mouseup."""
    _login_admin(app, client)
    page_id = _page(client)
    body = client.get(f"/admin/designer/{page_id}/edit").data.decode()
    assert "elementFromPoint" in body
    assert "function slotUnder(" in body
    # O drag HTML5 saiu do componente de RAIZ (que tem mousedown com
    # preventDefault). No Patch 2.3 ele volta, mas só no ramo aninhado,
    # onde não existe mousedown concorrente — por isso a asserção olha
    # o trecho de criação do elemento, não o arquivo inteiro.
    criacao = body.split("el.className = 'dsg-component'")[1][:500]
    assert "draggable" not in criacao


def test_elemento_arrastado_nao_intercepta_o_ponteiro(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    body = client.get(f"/admin/designer/{page_id}/edit").data.decode()
    assert "pointerEvents = 'none'" in body


def test_paleta_e_camadas_sao_colapsaveis(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    body = client.get(f"/admin/designer/{page_id}/edit").data.decode()
    assert "dsg-collapse-head" in body
    assert 'data-collapse-target="paletteBody"' in body
    assert 'data-collapse-target="layersBody"' in body
    assert "dsg-collapsed" in body


# ── Patch 2.3 — mais de um componente e reposicionar aninhado ────────

def test_render_nao_usa_foreach_com_referencia_direta(app, client):
    """Achado real: `childrenOf(null).forEach(renderComponent)` passa
    (item, indice, array) — a partir do SEGUNDO componente de raiz o
    índice chegava como `parentSlot`, o componente era tratado como
    aninhado e `(1).appendChild(el)` estourava, quebrando o render
    inteiro. Sintoma: só funcionava com um componente na página."""
    _login_admin(app, client)
    page_id = _page(client)
    body = client.get(f"/admin/designer/{page_id}/edit").data.decode()
    assert "forEach(function (c) { renderComponent(c); })" in body


def test_varios_componentes_de_raiz_convivem(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    for _ in range(3):
        assert _add(client, page_id, "label").status_code == 200

    resp = client.get(f"/admin/designer/{page_id}/components")
    raizes = [c for c in resp.get_json()["components"] if c["parent_id"] is None]
    assert len(raizes) == 3
    assert sorted(c["order_index"] for c in raizes) == [0, 1, 2]


def test_varios_filhos_no_mesmo_container(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    card = _add(client, page_id, "card").get_json()["component"]
    a = _add(client, page_id, "label").get_json()["component"]
    b = _add(client, page_id, "badge").get_json()["component"]

    for comp in (a, b):
        resp = client.post(f"/admin/designer/component/{comp['id']}/move-to",
                           json={"parent_id": card["id"]})
        assert resp.status_code == 200

    with app.app_context():
        filhos = DesignerComponent.query.filter_by(parent_id=card["id"]) \
            .order_by(DesignerComponent.order_index).all()
    assert len(filhos) == 2
    assert [f.order_index for f in filhos] == [0, 1]


def test_componente_aninhado_e_arrastavel(app, client):
    """Aninhado não tem arrasto por mousedown (quem posiciona é o pai),
    então pode usar drag HTML5 sem o conflito do Patch 2.2 — é assim
    que ele volta a ser reposicionável."""
    _login_admin(app, client)
    page_id = _page(client)
    body = client.get(f"/admin/designer/{page_id}/edit").data.decode()
    trecho = body.split("if (nested) {")[1][:900]
    assert "draggable" in trecho
    assert "dragstart" in trecho


def test_canvas_aceita_drop_para_devolver_a_raiz(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    body = client.get(f"/admin/designer/{page_id}/edit").data.decode()
    assert "canvas.addEventListener('drop'" in body
    assert "moveComponentTo(dragSourceId, null" in body
