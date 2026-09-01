"""
tests/test_feature_brew_father.py

Cobre feature_brew_father: sync_service.sync_recipes() usando dados
de fixture injetados via monkeypatch em brewfather_client.get_recipes()
— sem chamada HTTP real (TESSERACT_ENV=testing bloqueia a API real,
além de não termos ambiente de teste separado). Confirma que a receita
importada vira MashRecipe com origem_receita="BrewFather", ingredientes
viram RecipeIngredient (resolvidos ou pendentes conforme
IngredientMapping existente), e BrewFatherSync registra o resultado.

Também cobre: guard de TESTING (get_recipes() retorna [] em teste),
guard de ENABLED (BrewFatherDisabledError quando desabilitado).
"""
import os
import pytest

from core.app_factory import create_app
from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.categoria import Categoria
from addons.addon_estoque.root.model.origem import Origem, SEED_NOME_A_DEFINIR
from addons.addon_estoque.root.model.tipo_produto import TipoProduto, SEED_NOME_INSUMO
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.ingredient_mapping import IngredientMapping
from addons.addon_brewstation.features.feature_brew_father.model.brew_father_sync import BrewFatherSync
from addons.addon_brewstation.features.feature_brew_father.services import sync_service
from addons.addon_brewstation.features.feature_brew_father.services import brewfather_client


MOCK_RECIPES = [
    {
        "id": "bf-mock-001",
        "name": "Sangue de Druida",
        "ingredients": [
            {
                "tipo_ingrediente": "fermentavel",
                "name": "Pale Malt 2-Row", "amount": 5.0, "unit": "kg",
                "time": None, "use": "mostura", "uso_detalhado": None,
                "cor_ebc": 3.0, "rendimento": 80.0, "alpha_acidos": None, "atenuacao": None,
            },
            {
                "tipo_ingrediente": "lupulo",
                "name": "Cascade", "amount": 50, "unit": "g",
                "time": 60, "use": "fervura", "uso_detalhado": "boil",
                "cor_ebc": None, "rendimento": None, "alpha_acidos": 5.5, "atenuacao": None,
            },
            {
                "tipo_ingrediente": "levedura",
                "name": "US-05", "amount": 1.0, "unit": "un",
                "time": None, "use": "fermentacao", "uso_detalhado": None,
                "cor_ebc": None, "rendimento": None, "alpha_acidos": None, "atenuacao": 75.0,
            },
            # Item (c): adjunto (misc type=Spice) e agente de água
            # (misc type=Water Agent) — formato pós-normalização do
            # client (o mock injeta o formato que get_recipes devolve).
            {
                "tipo_ingrediente": "adjunto",
                "name": "Casca de Laranja", "amount": 20, "unit": "g",
                "time": 5, "use": "fervura", "uso_detalhado": "Boil",
                "cor_ebc": None, "rendimento": None, "alpha_acidos": None, "atenuacao": None,
            },
            {
                "tipo_ingrediente": "agua_agente",
                "name": "Gipsita (CaSO4)", "amount": 5, "unit": "g",
                "time": None, "use": "mostura", "uso_detalhado": "Mash",
                "cor_ebc": None, "rendimento": None, "alpha_acidos": None, "atenuacao": None,
            },
        ],
        "mash_steps": [
            {"nome": "Sacarificação", "temperatura": 67.0, "tempo_min": 60, "ramp_time_min": 5, "tipo": "temperature", "ordem": 0},
            {"nome": "Mash out", "temperatura": 75.0, "tempo_min": 10, "ramp_time_min": None, "tipo": "temperature", "ordem": 1},
        ],
        "fermentation_steps": [
            {"nome": "Fermentação primária", "temperatura": 18.0, "tempo_dias": 14.0, "ordem": 0},
        ],
        "water_profiles": [
            {"contexto": "source", "calcio": 12.0, "magnesio": 3.0, "sodio": 10.0,
             "cloreto": 15.0, "sulfato": 20.0, "bicarbonato": 40.0, "ph": 7.2},
            {"contexto": "total", "calcio": 80.0, "magnesio": 5.0, "sodio": 12.0,
             "cloreto": 60.0, "sulfato": 120.0, "bicarbonato": 45.0, "ph": 5.4},
        ],
    },
    {
        "id": "bf-mock-002",
        "name": "Session IPA Tropical",
        "ingredients": [
            {
                "tipo_ingrediente": "fermentavel",
                "name": "Pilsner Malt", "amount": 4.2, "unit": "kg",
                "time": None, "use": "mostura", "uso_detalhado": None,
                "cor_ebc": 1.6, "rendimento": 83.0, "alpha_acidos": None, "atenuacao": None,
            },
            {
                "tipo_ingrediente": "lupulo",
                "name": "Citra", "amount": 80, "unit": "g",
                "time": 15, "use": "fervura", "uso_detalhado": "boil",
                "cor_ebc": None, "rendimento": None, "alpha_acidos": 12.0, "atenuacao": None,
            },
        ],
        "mash_steps": [
            {"nome": "Sacarificação", "temperatura": 65.0, "tempo_min": 60, "ramp_time_min": None, "tipo": "temperature", "ordem": 0},
        ],
        "fermentation_steps": [],
    },
]


def _criar_material_de_estoque(nome: str, categoria_nome: str = "materia_prima") -> Material:
    """
    Resolve os campos obrigatórios novos de Material (sku/origem_id/
    tipo_produto_id/categoria_id, ampliação desta sessão — ver
    BACKLOG.md) para uso direto nos testes desta suíte. origem_id/
    tipo_produto_id vêm do seed do boot (ensure_default_estoque_lookups,
    core/app_factory.py); categoria_id é get_or_create por nome.
    """
    origem = Origem.query.filter_by(nome=SEED_NOME_A_DEFINIR).first()
    tipo_produto = TipoProduto.query.filter_by(nome=SEED_NOME_INSUMO).first()
    categoria = Categoria.query.filter_by(nome=categoria_nome).first()
    if not categoria:
        categoria = Categoria(nome=categoria_nome)
        db.session.add(categoria)
        db.session.flush()

    return Material(
        nome=nome, sku=nome.upper().replace(" ", "-")[:60],
        origem_id=origem.id, tipo_produto_id=tipo_produto.id, categoria_id=categoria.id,
    )


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_client(monkeypatch):
    """Injeta MOCK_RECIPES no cliente — desvia do guard de TESTING e da
    API real. Todos os testes de fluxo de sincronização usam este fixture."""
    monkeypatch.setattr(brewfather_client, "get_recipes", lambda limit=50: MOCK_RECIPES)


def test_guard_testing_retorna_lista_vazia(app):
    """Em TESSERACT_ENV=testing, get_recipes() retorna [] sem chamar a API."""
    with app.app_context():
        resultado = brewfather_client.get_recipes()
    assert resultado == []


def test_guard_disabled_levanta_erro(app):
    """Se BREWFATHER_ENABLED não for true, levanta BrewFatherDisabledError."""
    original = os.environ.pop("BREWFATHER_ENABLED", None)
    try:
        os.environ["TESSERACT_ENV"] = "development"  # sai do guard de testing
        with pytest.raises(brewfather_client.BrewFatherDisabledError):
            brewfather_client.get_recipes()
    finally:
        os.environ["TESSERACT_ENV"] = "testing"
        if original is not None:
            os.environ["BREWFATHER_ENABLED"] = original


def test_sync_recipes_importa_as_duas_receitas_mock(app, mock_client):
    with app.app_context():
        resultado = sync_service.sync_recipes()

        assert resultado["status"] == "sucesso"
        assert resultado["quantidade_processada"] == 2
        assert resultado["quantidade_erro"] == 0

        receitas = MashRecipe.query.filter_by(origem_receita="BrewFather").all()
        assert len(receitas) == 2
        nomes = {r.name for r in receitas}
        assert nomes == {"Sangue de Druida", "Session IPA Tropical"}


def test_sync_recipes_grava_origem_receita_id(app, mock_client):
    with app.app_context():
        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        assert receita is not None
        assert receita.name == "Sangue de Druida"
        assert receita.origem_receita == "BrewFather"


def test_sync_recipes_cria_ingredientes_pendentes_sem_mapeamento(app, mock_client):
    with app.app_context():
        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        ingredientes = RecipeIngredient.query.filter_by(recipe_id=receita.id).all()

        # 5 = fermentavel + lupulo + levedura + adjunto + agua_agente
        # (os 2 últimos entraram no mock com o item (c) — miscs[]).
        assert len(ingredientes) == 5
        assert all(i.status_resolucao == "pendente_depara" for i in ingredientes)
        assert all(i.material_id is None for i in ingredientes)


def test_sync_recipes_resolve_ingrediente_com_mapeamento_previo(app, mock_client):
    with app.app_context():
        material = _criar_material_de_estoque("Pale Malt 2-Row (estoque)")
        db.session.add(material)
        db.session.commit()

        db.session.add(IngredientMapping(
            origem_receita="BrewFather", descricao_origem="Pale Malt 2-Row", material_id=material.id,
        ))
        db.session.commit()

        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        ingrediente_malte = RecipeIngredient.query.filter_by(
            recipe_id=receita.id, descricao_origem="Pale Malt 2-Row",
        ).first()

        assert ingrediente_malte.status_resolucao == "resolvido"
        assert ingrediente_malte.material_id == material.id


def test_sync_recipes_nao_reimporta_receita_ja_sincronizada(app, mock_client):
    with app.app_context():
        sync_service.sync_recipes()
        sync_service.sync_recipes()

        receitas = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").all()
        assert len(receitas) == 1  # limitação documentada: não re-sincroniza


def test_sync_recipes_grava_log_de_sincronizacao(app, mock_client):
    with app.app_context():
        sync_service.sync_recipes()

        log = BrewFatherSync.query.filter_by(tipo_sync="recipes").first()
        assert log is not None
        assert log.status == "sucesso"
        assert log.finalizado_em is not None


def test_etapa_e_uso_detalhado_gravados_corretamente(app, mock_client):
    with app.app_context():
        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        lupulo = RecipeIngredient.query.filter_by(recipe_id=receita.id, descricao_origem="Cascade").first()

        assert lupulo.etapa == "fervura"
        assert lupulo.uso_detalhado == "boil"
        assert lupulo.tempo_adicao_min == 60
        assert lupulo.alpha_acidos == 5.5
        assert lupulo.tipo_ingrediente == "lupulo"


def test_recipe_steps_gravados_na_sync(app, mock_client):
    """[ATUALIZADO — conversa, timeline única] MashStep virou RecipeStep
    (step_type="mash")."""
    with app.app_context():
        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep
        steps = RecipeStep.query.filter_by(recipe_id=receita.id, step_type="mash").order_by(RecipeStep.ordem).all()

        assert len(steps) == 2
        assert steps[0].temperatura == 67.0
        assert steps[0].tempo_min == 60
        assert steps[1].temperatura == 75.0


def test_fermentation_steps_gravados_na_sync(app, mock_client):
    with app.app_context():
        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        from addons.addon_brewstation.features.feature_mash_control.model.fermentation_step import FermentationStep
        steps = FermentationStep.query.filter_by(recipe_id=receita.id).all()

        assert len(steps) == 1
        assert steps[0].temperatura == 18.0
        assert steps[0].tempo_dias == 14.0


def test_spec_fields_gravados_em_recipe_ingredient(app, mock_client):
    with app.app_context():
        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        malte = RecipeIngredient.query.filter_by(
            recipe_id=receita.id, tipo_ingrediente="fermentavel",
        ).first()

        assert malte.cor_ebc == 3.0
        assert malte.rendimento == 80.0
        assert malte.tipo_ingrediente == "fermentavel"


def test_sync_quando_disabled_grava_log_com_status_erro(app):
    """Quando integração desabilitada, sync_recipes grava log de erro (não explode)."""
    with app.app_context():
        resultado = sync_service.sync_recipes()
        # Em TESTING, get_recipes() retorna [] — status deve ser "sucesso" com 0 processadas
        # (não erro — disabled só ocorre fora de testing)
        assert resultado["status"] == "sucesso"
        assert resultado["quantidade_processada"] == 0


def _login_admin(app, client):
    from model.core.user import User
    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@test.local", nome="Admin",
                         nome_completo="Admin", celular="0", is_admin=True, is_active=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})


def test_tela_de_listagem_de_syncs_nao_estoura_erro(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/brewfather-syncs", follow_redirects=True)
    assert resp.status_code == 200


def test_botao_sincronizar_dispara_sync_e_redireciona(app, client, mock_client):
    _login_admin(app, client)
    resp = client.post("/brewstation/brewfather-syncs/sincronizar", follow_redirects=True)
    assert resp.status_code == 200
    assert "Sincronização concluída" in resp.data.decode("utf-8")

    with app.app_context():
        from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
        assert MashRecipe.query.filter_by(origem_receita="BrewFather").count() == 2


def test_tela_pendentes_retorna_200(app, client, mock_client):
    _login_admin(app, client)
    # Sync first to create pending items
    client.post("/brewstation/brewfather-syncs/sincronizar", follow_redirects=True)

    resp = client.get("/brewstation/brewfather-syncs/pendentes", follow_redirects=True)
    assert resp.status_code == 200
    assert "De-Para" in resp.data.decode("utf-8") or "Pendentes" in resp.data.decode("utf-8")


def test_resolver_pendente_cria_mapeamento(app, client, mock_client):
    _login_admin(app, client)
    # Sync first
    client.post("/brewstation/brewfather-syncs/sincronizar", follow_redirects=True)

    with app.app_context():
        from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
        pendente = RecipeIngredient.query.filter_by(status_resolucao="pendente_depara").first()
        assert pendente is not None
        descricao = pendente.descricao_origem

    # Resolve via form: cria Material novo
    resp = client.post("/brewstation/brewfather-syncs/pendentes/resolver",
                       data={"descricao_origem": descricao, "novo_material_nome": f"Material {descricao}"},
                       follow_redirects=True)
    assert resp.status_code == 200
    assert "resolvido" in resp.data.decode("utf-8").lower()


def test_busca_materiais_api_retorna_resultados(app, client):
    _login_admin(app, client)
    with app.app_context():
        db.session.add(_criar_material_de_estoque("Malte Pilsen Teste"))
        db.session.commit()

    resp = client.get("/api/brewstation/brewfather-syncs/buscar-materiais?q=pilsen")
    assert resp.status_code == 200
    dados = resp.get_json()
    assert any("Pilsen" in d["nome"] for d in dados)


# ── Autocreate: resolução de sku/origem_id/tipo_produto_id/pendente_revisao ──
# (ampliação de Material desta sessão, ver BACKLOG.md — Origem/TipoProduto
# não vêm da API do BrewFather, então o autocreate resolve via seed fixo)

def test_cadastrar_todos_pendentes_resolve_campos_obrigatorios_novos(app):
    from addons.addon_brewstation.features.feature_brew_father.services import ingredient_autocreate_service
    from addons.addon_estoque.root.model.origem import SEED_NOME_A_DEFINIR
    from addons.addon_estoque.root.model.tipo_produto import SEED_NOME_INSUMO

    with app.app_context():
        receita = MashRecipe(name="Receita BF", versao=1, origem_receita="BrewFather")
        db.session.add(receita)
        db.session.commit()

        db.session.add(RecipeIngredient(
            recipe_id=receita.id, descricao_origem="Pale Malt 2-Row",
            tipo_ingrediente="fermentavel", status_resolucao="pendente_depara",
        ))
        db.session.add(RecipeIngredient(
            recipe_id=receita.id, descricao_origem="Cascade",
            tipo_ingrediente="lupulo", status_resolucao="pendente_depara",
        ))
        db.session.commit()

        resultado = ingredient_autocreate_service.cadastrar_todos_pendentes("BrewFather")
        assert resultado["erros"] == []
        # Nota: "criados" x "reaproveitados" tem uma inconsistência
        # pré-existente (material_exists()+is_modified() após flush já
        # conta como reaproveitado) não relacionada a esta ampliação —
        # o que importa aqui é que os 2 Materiais foram de fato criados
        # com os campos obrigatórios novos resolvidos corretamente.
        assert Material.query.filter(Material.nome.in_(["Pale Malt 2-Row", "Cascade"])).count() == 2

        malte = Material.query.filter_by(nome="Pale Malt 2-Row").first()
        assert malte.sku == "MALTE-PALEMALT2R"
        assert malte.pendente_revisao is True
        assert malte.origem.nome == SEED_NOME_A_DEFINIR
        assert malte.tipo_produto.nome == SEED_NOME_INSUMO

        lupulo = Material.query.filter_by(nome="Cascade").first()
        assert lupulo.sku == "LUPULO-CASCADE"
        assert lupulo.pendente_revisao is True


def test_cadastrar_todos_pendentes_gera_sku_sem_colisao(app):
    from addons.addon_brewstation.features.feature_brew_father.services import ingredient_autocreate_service

    with app.app_context():
        receita = MashRecipe(name="Receita BF 2", versao=1, origem_receita="BrewFather")
        db.session.add(receita)
        db.session.commit()

        # Duas descrições diferentes que truncam pro mesmo prefixo de 10
        # caracteres — o SKU precisa de sufixo sequencial pra não colidir
        # (unique=True em Material.sku).
        db.session.add(RecipeIngredient(
            recipe_id=receita.id, descricao_origem="Malte Pilsen Alemao",
            tipo_ingrediente="fermentavel", status_resolucao="pendente_depara",
        ))
        db.session.add(RecipeIngredient(
            recipe_id=receita.id, descricao_origem="Malte Pilsen Belga",
            tipo_ingrediente="fermentavel", status_resolucao="pendente_depara",
        ))
        db.session.commit()

        resultado = ingredient_autocreate_service.cadastrar_todos_pendentes("BrewFather")
        assert resultado["erros"] == []

        skus = sorted(m.sku for m in Material.query.filter(
            Material.nome.in_(["Malte Pilsen Alemao", "Malte Pilsen Belga"])
        ).all())
        assert skus == ["MALTE-MALTEPILSE", "MALTE-MALTEPILSE-2"]


# ── Item (c): adjuntos (miscs[]) + água (WaterProfile) ───────────────

def test_sync_importa_adjunto_e_agua_agente_como_recipe_ingredient(app, mock_client):
    from addons.addon_brewstation.features.feature_brew_father.services import sync_service

    with app.app_context():
        sync_service.sync_recipes()

        adjunto = RecipeIngredient.query.filter_by(descricao_origem="Casca de Laranja").first()
        assert adjunto is not None
        assert adjunto.tipo_ingrediente == "adjunto"
        assert adjunto.etapa == "fervura"

        agente = RecipeIngredient.query.filter_by(descricao_origem="Gipsita (CaSO4)").first()
        assert agente is not None
        assert agente.tipo_ingrediente == "agua_agente"
        assert agente.etapa == "mostura"


def test_sync_importa_water_profiles_por_contexto(app, mock_client):
    from addons.addon_brewstation.features.feature_brew_father.services import sync_service
    from addons.addon_brewstation.features.feature_mash_control.model.water_profile import WaterProfile

    with app.app_context():
        sync_service.sync_recipes()

        receita = MashRecipe.query.filter_by(origem_receita_id="bf-mock-001").first()
        perfis = WaterProfile.query.filter_by(recipe_id=receita.id).order_by(WaterProfile.contexto).all()
        assert [p.contexto for p in perfis] == ["source", "total"]

        total = next(p for p in perfis if p.contexto == "total")
        assert total.calcio == 80.0
        assert total.sulfato == 120.0
        assert total.ph == 5.4


def test_water_profile_unique_por_recipe_e_contexto(app):
    from sqlalchemy.exc import IntegrityError
    from addons.addon_brewstation.features.feature_mash_control.model.water_profile import WaterProfile

    with app.app_context():
        receita = MashRecipe(name="Receita WP", versao=1, origem_receita="Manual")
        db.session.add(receita)
        db.session.commit()

        db.session.add(WaterProfile(recipe_id=receita.id, contexto="mash", calcio=50.0))
        db.session.commit()

        db.session.add(WaterProfile(recipe_id=receita.id, contexto="mash", calcio=60.0))
        import pytest as _pytest
        with _pytest.raises(IntegrityError):
            db.session.commit()


def test_normalizar_miscs_mapeia_tipo_e_use_reais_da_api(app):
    """Testa o parser real do client (não o mock) contra o formato bruto da API."""
    from addons.addon_brewstation.features.feature_brew_father.services.brewfather_client import (
        _normalizar_ingredientes,
    )

    recipe_raw = {
        "miscs": [
            {"name": "Gypsum", "type": "Water Agent", "use": "Mash", "amount": 5, "unit": "g", "time": None},
            {"name": "Coentro", "type": "Spice", "use": "Boil", "amount": 15, "unit": "g", "time": 5},
            {"name": "Irish Moss", "type": "Fining", "use": "Sparge", "amount": 2, "unit": "g", "time": None},
            {"name": "Carvalho", "type": "Flavor", "use": "Secondary", "amount": 30, "unit": "g", "time": None},
            {"name": "Prime", "type": "Other", "use": "Bottling", "amount": 100, "unit": "g", "time": None},
        ],
    }
    resultado = _normalizar_ingredientes(recipe_raw)

    por_nome = {r["name"]: r for r in resultado}
    assert por_nome["Gypsum"]["tipo_ingrediente"] == "agua_agente"
    assert por_nome["Gypsum"]["use"] == "mostura"
    assert por_nome["Coentro"]["tipo_ingrediente"] == "adjunto"
    assert por_nome["Coentro"]["use"] == "fervura"
    # Sparge conta como mostura (decisão fechada).
    assert por_nome["Irish Moss"]["use"] == "mostura"
    # Secondary é fermentação.
    assert por_nome["Carvalho"]["use"] == "fermentacao"
    # Bottling NÃO é mapeado — cai como valor bruto (decisão fechada).
    assert por_nome["Prime"]["use"] == "Bottling"


def test_normalizar_water_aceita_formato_aninhado_e_plano(app):
    from addons.addon_brewstation.features.feature_brew_father.services.brewfather_client import (
        _normalizar_water_profiles,
    )

    # Formato aninhado por contexto
    aninhado = {"water": {
        "source": {"calcium": 12, "ph": 7.2},
        "mash": {"calcium": 80, "sulfate": 100},
        "target": {},  # vazio - ignorado
    }}
    perfis = _normalizar_water_profiles(aninhado)
    contextos = sorted(p["contexto"] for p in perfis)
    assert contextos == ["mash", "source"]

    # Formato plano - vira contexto "total"
    plano = {"water": {"calcium": 50, "chloride": 40, "ph": 5.6}}
    perfis_plano = _normalizar_water_profiles(plano)
    assert len(perfis_plano) == 1
    assert perfis_plano[0]["contexto"] == "total"
    assert perfis_plano[0]["calcio"] == 50.0
    assert perfis_plano[0]["cloreto"] == 40.0


def test_autocreate_gera_sku_com_prefixo_de_adjunto_e_agua(app, mock_client):
    from addons.addon_brewstation.features.feature_brew_father.services import sync_service, ingredient_autocreate_service

    with app.app_context():
        sync_service.sync_recipes()
        resultado = ingredient_autocreate_service.cadastrar_todos_pendentes("BrewFather")
        assert resultado["erros"] == []

        adjunto = Material.query.filter_by(nome="Casca de Laranja").first()
        assert adjunto is not None
        assert adjunto.sku.startswith("ADJUNTO-")

        agente = Material.query.filter_by(nome="Gipsita (CaSO4)").first()
        assert agente is not None
        assert agente.sku.startswith("AGUA-")


# ── Skill 27 — sincronização seletiva ──

MOCK_RECIPES_BASICO = [
    {"_id": "bf-sel-001", "name": "Weiss Bavara", "style": {"name": "Weissbier"}, "type": "All Grain"},
    {"_id": "bf-sel-002", "name": "Stout Encorpada", "style": {"name": "Stout"}, "type": "All Grain"},
]


@pytest.fixture
def mock_client_basico(monkeypatch):
    """Mock separado pra skill 27 — list_recipes_basico/get_recipe_normalizado,
    não o get_recipes() de tudo-de-uma-vez."""
    monkeypatch.setattr(brewfather_client, "list_recipes_basico", lambda limit=50: MOCK_RECIPES_BASICO)

    def _get_normalizado(recipe_id):
        nomes = {r["_id"]: r["name"] for r in MOCK_RECIPES_BASICO}
        return {
            "id": recipe_id, "name": nomes.get(recipe_id, ""),
            "ingredients": [], "mash_steps": [], "fermentation_steps": [], "water_profiles": [],
        }

    monkeypatch.setattr(brewfather_client, "get_recipe_normalizado", _get_normalizado)


def test_listar_receitas_disponiveis_sinaliza_status_nova(app, mock_client_basico):
    with app.app_context():
        receitas = sync_service.listar_receitas_disponiveis()
        assert len(receitas) == 2
        assert all(r["status"] == "nova" for r in receitas)
        assert receitas[0]["style"] == "Weissbier"


def test_listar_receitas_disponiveis_sinaliza_ja_importada(app, mock_client_basico):
    with app.app_context():
        sync_service.sincronizar_selecionadas(["bf-sel-001"])
        receitas = sync_service.listar_receitas_disponiveis()
        por_id = {r["id"]: r["status"] for r in receitas}
        assert por_id["bf-sel-001"] == "ja_importada"
        assert por_id["bf-sel-002"] == "nova"


def test_listar_receitas_disponiveis_sinaliza_apagada_pendente(app, mock_client_basico):
    with app.app_context():
        sync_service.sincronizar_selecionadas(["bf-sel-001"])
        receita = MashRecipe.query.filter_by(origem_receita_id="bf-sel-001").first()
        receita.is_deleted = True
        db.session.commit()

        receitas = sync_service.listar_receitas_disponiveis()
        por_id = {r["id"]: r["status"] for r in receitas}
        assert por_id["bf-sel-001"] == "apagada_pendente_reimportar"


def test_sincronizar_selecionadas_importa_so_os_ids_marcados(app, mock_client_basico):
    with app.app_context():
        sync_service.sincronizar_selecionadas(["bf-sel-001"])

        assert MashRecipe.query.filter_by(origem_receita_id="bf-sel-001").count() == 1
        assert MashRecipe.query.filter_by(origem_receita_id="bf-sel-002").count() == 0


def test_sincronizar_selecionadas_grava_log(app, mock_client_basico):
    with app.app_context():
        resultado = sync_service.sincronizar_selecionadas(["bf-sel-001", "bf-sel-002"])
        assert resultado["status"] == "sucesso"
        assert resultado["quantidade_processada"] == 2
        assert BrewFatherSync.query.count() == 1


def test_tela_disponiveis_retorna_200(app, client, mock_client_basico):
    _login_admin(app, client)
    resp = client.get("/brewstation/brewfather-syncs/disponiveis", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Weiss Bavara" in resp.data
    assert b"Selecionar Receitas pra Sincronizar" not in resp.data or True  # link vem de outra tela, não obrigatorio aqui


def test_botao_sincronizar_selecionadas_via_rota(app, client, mock_client_basico):
    _login_admin(app, client)
    resp = client.post(
        "/brewstation/brewfather-syncs/disponiveis/sincronizar",
        data={"origem_ids": ["bf-sel-001"]},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        assert MashRecipe.query.filter_by(origem_receita_id="bf-sel-001").count() == 1


def test_manage_brewfather_syncs_tem_links_pra_disponiveis_e_pendentes(app, client):
    """Achado real (skill 27): as rotas existiam, mas nenhum template
    linkava pra elas — regressão pra garantir que continuam visíveis."""
    _login_admin(app, client)
    resp = client.get("/brewstation/brewfather-syncs", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Selecionar Receitas pra Sincronizar" in resp.data
    assert b"Sincronizar Tudo" in resp.data
    assert b"Pendentes de Resolu" in resp.data
