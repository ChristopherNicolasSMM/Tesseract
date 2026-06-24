"""
tests/test_theme_profile_roles_versioning.py

Cobre o bloco entregue nesta rodada: tema claro/escuro por usuário,
tela de perfil, gestão de Roles/Permissions, telas de versionamento
(histórico/diff/restauração), e paginação+filtro nas listas geradas
pelo CrudGen (smart-list-lite).
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.role import Role
from model.core.permission import Permission


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


# ── Tema / Perfil ────────────────────────────────────────────────────────────

def test_usuario_novo_tem_tema_claro_por_padrao(app):
    with app.app_context():
        user = User(
            username="x", email="x@test.local", nome="X", nome_completo="X X",
            celular="11900000000",
        )
        user.set_password("senha123")
        db.session.add(user)
        db.session.commit()
        assert user.theme == "light"


def test_update_theme_via_api(app, client):
    _login_admin(app, client)
    resp = client.post("/api/auth/update-theme", json={"theme": "dark"})
    assert resp.status_code == 200
    assert resp.get_json()["theme"] == "dark"

    with app.app_context():
        assert User.query.filter_by(username="admin").first().theme == "dark"


def test_update_theme_rejeita_valor_invalido(app, client):
    _login_admin(app, client)
    resp = client.post("/api/auth/update-theme", json={"theme": "azul"})
    assert resp.status_code == 422


def test_perfil_abre_e_mostra_dados_do_usuario_logado(app, client):
    _login_admin(app, client)
    resp = client.get("/perfil/")
    assert resp.status_code == 200
    assert b"admin" in resp.data


def test_perfil_atualiza_dados_proprios(app, client):
    _login_admin(app, client)
    resp = client.post(
        "/perfil/",
        data={
            "email": "novo@test.local", "nome": "Admin",
            "nome_completo": "Administrador Editado", "celular": "11999999999",
        },
        follow_redirects=True,
    )
    assert b"Administrador Editado" in resp.data


def test_perfil_troca_senha_com_senha_atual_correta(app, client):
    _login_admin(app, client)
    resp = client.post(
        "/perfil/senha",
        data={"current_password": "senha123", "new_password": "novaSenha456", "confirm_password": "novaSenha456"},
        follow_redirects=True,
    )
    assert b"alterada com sucesso" in resp.data

    client.post("/api/auth/logout")
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "novaSenha456"})
    assert resp.get_json()["success"] is True


def test_perfil_rejeita_troca_de_senha_com_senha_atual_errada(app, client):
    _login_admin(app, client)
    resp = client.post(
        "/perfil/senha",
        data={"current_password": "errada", "new_password": "novaSenha456", "confirm_password": "novaSenha456"},
        follow_redirects=True,
    )
    assert b"incorreta" in resp.data


# ── Roles / Permissions ──────────────────────────────────────────────────────

def test_criar_role_pela_tela(app, client):
    _login_admin(app, client)
    resp = client.post(
        "/admin/roles/", data={"name": "brewmaster", "description": "teste"}, follow_redirects=True,
    )
    assert b"brewmaster" in resp.data
    with app.app_context():
        assert Role.query.filter_by(name="brewmaster").first() is not None


def test_nao_permite_dois_roles_com_mesmo_nome(app, client):
    _login_admin(app, client)
    client.post("/admin/roles/", data={"name": "brewmaster"})
    resp = client.post("/admin/roles/", data={"name": "brewmaster"}, follow_redirects=True)
    assert b"J\xc3\xa1 existe" in resp.data


def test_associar_permissoes_a_role(app, client):
    _login_admin(app, client)
    with app.app_context():
        role = Role(name="leitor")
        perm = Permission(name="teste.list")
        db.session.add_all([role, perm])
        db.session.commit()
        role_id, perm_id = role.id, perm.id

    client.post(f"/admin/roles/{role_id}/permissions", data={"permission_ids": [str(perm_id)]})

    with app.app_context():
        role = Role.query.get(role_id)
        assert "teste.list" in [p.name for p in role.permissions]


def test_nao_permite_excluir_role_com_usuario_atribuido(app, client):
    _login_admin(app, client)
    with app.app_context():
        role = Role(name="ocupado")
        admin = User.query.filter_by(username="admin").first()
        admin.roles.append(role)
        db.session.add(role)
        db.session.commit()
        role_id = role.id

    resp = client.post(f"/admin/roles/{role_id}/delete", follow_redirects=True)
    assert "Não é possível excluir".encode("utf-8") in resp.data

    with app.app_context():
        assert Role.query.get(role_id) is not None


# ── Versionamento ────────────────────────────────────────────────────────────

def test_versionamento_lista_arquivos_com_historico(app, client):
    _login_admin(app, client)
    with app.app_context():
        from core.versioning import snapshot_if_needed
        snapshot_if_needed("arquivo_teste.py", "conteudo a")
        snapshot_if_needed("arquivo_teste.py", "conteudo b")

    resp = client.get("/admin/versioning/")
    assert b"arquivo_teste.py" in resp.data


def test_versionamento_diff_mostra_alteracoes(app, client):
    _login_admin(app, client)
    with app.app_context():
        from core.versioning import snapshot_if_needed
        from model.core.code_snapshot import CodeSnapshot
        snapshot_if_needed("arquivo_diff.py", "linha original")
        snapshot_if_needed("arquivo_diff.py", "linha modificada")
        snaps = CodeSnapshot.query.filter_by(file_path="arquivo_diff.py").order_by(CodeSnapshot.created_at).all()
        id_a, id_b = snaps[0].id, snaps[1].id

    resp = client.get(f"/admin/versioning/history?file_path=arquivo_diff.py&a={id_a}&b={id_b}")
    assert b"-linha original" in resp.data
    assert b"+linha modificada" in resp.data


def test_versionamento_restaura_e_grava_no_disco(app, client, tmp_path):
    _login_admin(app, client)
    target = tmp_path / "restaura_teste.py"

    with app.app_context():
        from core.versioning import snapshot_if_needed
        from model.core.code_snapshot import CodeSnapshot
        snapshot_if_needed(str(target), "versao 1")
        snapshot_if_needed(str(target), "versao 2")
        old_id = CodeSnapshot.query.filter_by(file_path=str(target)).order_by(CodeSnapshot.created_at).first().id

    resp = client.post(f"/admin/versioning/restore/{old_id}", data={"file_path": str(target)}, follow_redirects=True)
    assert b"restaurada com sucesso" in resp.data
    assert target.read_text() == "versao 1"


# ── Paginação / filtro nas listas geradas (smart-list-lite) ────────────────

def test_lista_gerada_tem_filtro_de_busca(app, client):
    _login_admin(app, client)
    client.post("/brewstation/yeast-strains/", data={"name": "US-05"})
    client.post("/brewstation/yeast-strains/", data={"name": "Wyeast 1056"})

    resp = client.get("/brewstation/yeast-strains/?q=US-05")
    assert b"US-05" in resp.data
    assert b"Wyeast" not in resp.data


def test_lista_gerada_mostra_contador_de_registros(app, client):
    _login_admin(app, client)
    client.post("/brewstation/yeast-strains/", data={"name": "US-05"})
    resp = client.get("/brewstation/yeast-strains/")
    assert b"registro(s)" in resp.data


def test_novo_registro_fica_em_secao_recolhida(app, client):
    """
    O formulário de criação deve estar dentro de um <div class="collapse">
    — só visível ao clicar no botão "+", não exibido por padrão.
    """
    _login_admin(app, client)
    resp = client.get("/brewstation/yeast-strains/")
    assert b'class="collapse" id="novoRegistroForm"' in resp.data
