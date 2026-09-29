"""
tests/test_hide_legacy_mash_control_menu.py

Comando CLI de uso único (conversa — workspace consolidado por
Planta): `flask hide-legacy-mash-control-menu`. Desativa no menu as
3 atalhos de visualização absorvidos pelo workspace. O upgrade também
aplica esta transição em bancos existentes.
"""
from core.app_factory import create_app
from core.db import db
from model.core.transaction import Transaction


_EXPECTED_HIDDEN_CODES = {
    "TX_RECIPE_TIMELINE", "TX_DASHBOARD_VIEW", "TX_DASHBOARD_WIDGETS",
}


def test_hide_legacy_menu_desativa_as_3_transacoes_esperadas():
    app = create_app(env="testing")
    runner = app.test_cli_runner()

    result = runner.invoke(args=["hide-legacy-mash-control-menu"])
    assert result.exit_code == 0, result.output
    assert "Desativadas: 0" in result.output  # catálogo já as cria ocultas

    with app.app_context():
        for code in _EXPECTED_HIDDEN_CODES:
            tx = Transaction.query.filter_by(code=code).first()
            assert tx is not None, f"{code} não existe no banco"
            assert tx.is_active is False, f"{code} deveria estar inativa"


def test_hide_legacy_menu_preserva_cadastros_e_historicos():
    app = create_app(env="testing")
    runner = app.test_cli_runner()
    runner.invoke(args=["hide-legacy-mash-control-menu"])

    with app.app_context():
        for code in ("TX_MASH_RECIPES", "TX_BREW_PLANT_VESSELS", "TX_BREW_PLANT_MAPPINGS",
                     "TX_BREW_SESSIONS", "TX_BREW_SESSION_STEPS", "TX_BREW_SESSION_LOGS",
                     "TX_BREW_SESSION_ALARMS", "TX_AUTOMATION_RULES", "TX_AUTOMATION_RULE_LOGS",
                     "TX_DASHBOARD_LAYOUTS"):
            tx = Transaction.query.filter_by(code=code).first()
            assert tx is not None and tx.is_active is True, code


def test_hide_legacy_menu_nao_mexe_em_transacoes_fora_do_escopo():
    """Fermentação, Perfis de Água, Histórico de Receitas, De-Para de
    Ingredientes — nenhum foi absorvido por nenhuma aba, continuam
    ativas."""
    app = create_app(env="testing")
    runner = app.test_cli_runner()
    runner.invoke(args=["hide-legacy-mash-control-menu"])

    with app.app_context():
        for code in ["TX_WATER_PROFILES", "TX_RECIPE_HISTORYS", "TX_INGREDIENT_MAPPINGS"]:
            tx = Transaction.query.filter_by(code=code).first()
            assert tx is not None
            assert tx.is_active is True, f"{code} não deveria ter sido desativada"


def test_hide_legacy_menu_nao_mexe_no_workspace_nem_no_bridge():
    """A própria transação do workspace (TX_PLANT_WORKSPACE) e o
    Cadastro Primário (TX_BRIDGE_IMPORT) não fazem parte da lista —
    continuam ativas."""
    app = create_app(env="testing")
    runner = app.test_cli_runner()
    runner.invoke(args=["hide-legacy-mash-control-menu"])

    with app.app_context():
        for code in ["TX_PLANT_WORKSPACE", "TX_BRIDGE_IMPORT"]:
            tx = Transaction.query.filter_by(code=code).first()
            assert tx is not None
            assert tx.is_active is True


def test_hide_legacy_menu_dry_run_nao_grava_nada():
    app = create_app(env="testing")
    runner = app.test_cli_runner()
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_RECIPE_TIMELINE").first()
        tx.is_active = True
        db.session.commit()

    result = runner.invoke(args=["hide-legacy-mash-control-menu", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "[DRY RUN]" in result.output
    assert "Desativadas: 1" in result.output

    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_RECIPE_TIMELINE").first()
        assert tx.is_active is True


def test_hide_legacy_menu_rodar_duas_vezes_e_idempotente():
    app = create_app(env="testing")
    runner = app.test_cli_runner()
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_RECIPE_TIMELINE").first()
        tx.is_active = True
        db.session.commit()

    first = runner.invoke(args=["hide-legacy-mash-control-menu"])
    assert "Desativadas: 1" in first.output

    second = runner.invoke(args=["hide-legacy-mash-control-menu"])
    assert second.exit_code == 0, second.output
    assert "Desativadas: 0" in second.output
    assert "Já estavam inativas" in second.output

    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_RECIPE_TIMELINE").first()
        assert tx.is_active is False


def test_hide_legacy_menu_rotas_continuam_funcionando_depois():
    """As telas em si nunca deixam de existir — só saem do menu. Sanity
    check: a rota /brewstation/brew-sessions/ continua respondendo
    200 depois do comando."""
    app = create_app(env="testing")
    runner = app.test_cli_runner()
    runner.invoke(args=["hide-legacy-mash-control-menu"])

    with app.app_context():
        from model.core.user import User
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@test.local", nome="Admin",
                         nome_completo="Admin", celular="0", is_admin=True, is_active=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()

    client = app.test_client()
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    resp = client.get("/brewstation/brew-sessions/")
    assert resp.status_code == 200
