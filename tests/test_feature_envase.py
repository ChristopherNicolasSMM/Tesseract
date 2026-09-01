"""
tests/test_feature_envase.py

Cobre feature_envase: Envase (agora com material_resultante_id — skill 26)
e o fluxo novo de envase_estoque_service.registrar_envase() — baixa
síncrona dos componentes resolvidos pela Composição do Material
resultante, fallback de confirmação de insumo, e o cálculo de custo
de industrialização.

ItemEnvase (tabela antiga) não é mais criado por registrar_envase() —
fica só como histórico do que existia antes da skill 26.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.categoria import Categoria
from addons.addon_estoque.root.model.origem import Origem, SEED_NOME_A_DEFINIR
from addons.addon_estoque.root.model.tipo_produto import TipoProduto, SEED_NOME_INSUMO
from addons.addon_estoque.root.model.composicao import Composicao
from addons.addon_estoque.root.services import estoque_service as material_movement_service
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_envase.model.envase import Envase
from addons.addon_brewstation.features.feature_envase.model.item_envase import ItemEnvase
from addons.addon_brewstation.features.feature_envase.services import envase_estoque_service as svc
from addons.addon_brewstation.features.feature_mash_control.services import ingredient_consumption_service


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _ids_lookup_padrao(categoria_nome: str = "materia_prima_envase") -> dict:
    """Mesmo raciocínio de tests/test_addon_estoque.py::_ids_lookup_padrao
    — resolve por descricao/codigo, não por `nome` (que não existe mais
    em Categoria/TipoProduto)."""
    origem = Origem.query.filter_by(nome=SEED_NOME_A_DEFINIR).first()
    tipo_produto = TipoProduto.query.filter_by(descricao=SEED_NOME_INSUMO).first()
    categoria = Categoria.query.filter_by(descricao=categoria_nome).first()
    if not categoria:
        categoria = Categoria(
            descricao=categoria_nome, codigo=categoria_nome.upper().replace(" ", "_"),
            tipo_produto_id=tipo_produto.id,
        )
        db.session.add(categoria)
        db.session.flush()
    return {"origem_id": origem.id, "tipo_produto_id": tipo_produto.id, "categoria_id": categoria.id}


def _criar_material(nome: str, **kwargs) -> Material:
    material = Material(nome=nome, sku=nome.upper().replace(" ", "-"), **_ids_lookup_padrao(), **kwargs)
    db.session.add(material)
    db.session.commit()
    return material


def _criar_material_com_estoque(nome="Garrafa 600ml", quantidade_inicial=100, custo_unitario=1.5, **kwargs) -> Material:
    material = _criar_material(nome, unidade_medida="un", **kwargs)
    material_movement_service.registrar_movimentacao(material.id, "entrada", quantidade_inicial, custo_unitario=custo_unitario)
    return material


def _criar_lote(nome="IPA Tropical", com_ingrediente=None):
    """`com_ingrediente`: (material, quantidade) opcional — vincula um
    RecipeIngredient já resolvido, pra testar o fluxo de confirmação
    de insumo."""
    receita = MashRecipe(name=nome, versao=1, origem_receita="Manual")
    db.session.add(receita)
    db.session.commit()

    if com_ingrediente:
        material, quantidade = com_ingrediente
        db.session.add(RecipeIngredient(
            recipe_id=receita.id, descricao_origem=material.nome,
            material_id=material.id, quantidade=quantidade, status_resolucao="resolvido",
        ))
        db.session.commit()

    lote = BrewSession(name=f"Sessão {nome}", recipe_id=receita.id, status="concluida")
    db.session.add(lote)
    db.session.commit()
    return lote


def _criar_material_resultante(nome="Growler 1L Teste", volume_real=1.0, componentes=None) -> Material:
    """Material acabado com volume_real preenchido + Composição
    (lista de (material_componente, quantidade))."""
    resultante = _criar_material(nome, volume_real=volume_real, unidade_medida_volume_real="L")
    for componente, quantidade in (componentes or []):
        db.session.add(Composicao(
            material_pai_id=resultante.id, material_componente_id=componente.id, quantidade=quantidade,
        ))
    db.session.commit()
    return resultante


# ── registrar_envase — caminho feliz com Composição ──

def test_registrar_envase_cria_envase_com_material_resultante(app):
    with app.app_context():
        lote = _criar_lote()
        tampinha = _criar_material_com_estoque(nome="Tampinha Envase1", quantidade_inicial=200)
        resultante = _criar_material_resultante(componentes=[(tampinha, 1)])

        resultado = svc.registrar_envase(lote.id, resultante.id, quantidade_litros=10, tipo_envase="growler")

        assert resultado["envase"]["lote_id"] == lote.id
        assert resultado["envase"]["material_resultante_id"] == resultante.id
        assert resultado["unidades_geradas"] == 10  # 10 litros / 1L por unidade
        assert resultado["componentes_baixados"] == 1
        # ItemEnvase não é mais criado por este fluxo
        assert ItemEnvase.query.filter_by(envase_id=resultado["envase"]["id"]).count() == 0


def test_registrar_envase_da_baixa_nos_componentes_da_composicao(app):
    with app.app_context():
        lote = _criar_lote()
        tampinha = _criar_material_com_estoque(nome="Tampinha Envase2", quantidade_inicial=200)
        resultante = _criar_material_resultante(componentes=[(tampinha, 1)])

        svc.registrar_envase(lote.id, resultante.id, quantidade_litros=10)

        # 10 litros / 1L por unidade = 10 unidades; 1 tampinha por unidade = 10 baixadas
        saldo = material_movement_service.consultar_saldo(tampinha.id)
        assert saldo["quantidade_atual"] == 190


def test_registrar_envase_multiplos_componentes(app):
    with app.app_context():
        lote = _criar_lote()
        tampinha = _criar_material_com_estoque(nome="Tampinha Envase3", quantidade_inicial=50)
        rotulo = _criar_material_com_estoque(nome="Rótulo Envase3", quantidade_inicial=50)
        resultante = _criar_material_resultante(componentes=[(tampinha, 1), (rotulo, 1)])

        resultado = svc.registrar_envase(lote.id, resultante.id, quantidade_litros=5)

        assert resultado["componentes_baixados"] == 2
        assert material_movement_service.consultar_saldo(tampinha.id)["quantidade_atual"] == 45
        assert material_movement_service.consultar_saldo(rotulo.id)["quantidade_atual"] == 45


# ── validações ──

def test_registrar_envase_lote_inexistente_levanta_erro(app):
    with app.app_context():
        resultante = _criar_material_resultante()
        with pytest.raises(svc.LoteNaoEncontradoError):
            svc.registrar_envase(99999, resultante.id, quantidade_litros=1)


def test_registrar_envase_material_resultante_inexistente_levanta_erro(app):
    with app.app_context():
        lote = _criar_lote()
        with pytest.raises(svc.MaterialNaoEncontradoError):
            svc.registrar_envase(lote.id, 99999, quantidade_litros=1)
        assert Envase.query.count() == 0


def test_registrar_envase_sem_volume_real_levanta_erro(app):
    with app.app_context():
        lote = _criar_lote()
        resultante = _criar_material("Growler Sem Volume")  # volume_real não preenchido
        with pytest.raises(svc.VolumeRealNaoConfiguradoError):
            svc.registrar_envase(lote.id, resultante.id, quantidade_litros=10)


# ── fallback de confirmação de insumo (skill 26, seção 2.1) ──

def test_registrar_envase_confirma_insumo_automaticamente_se_pendente(app):
    with app.app_context():
        malte = _criar_material_com_estoque(nome="Malte Envase Fallback", quantidade_inicial=100, custo_unitario=10.0)
        lote = _criar_lote(com_ingrediente=(malte, 5))
        resultante = _criar_material_resultante()

        assert lote.insumos_baixados_em is None

        svc.registrar_envase(lote.id, resultante.id, quantidade_litros=10)

        db.session.refresh(lote)
        assert lote.insumos_baixados_em is not None
        assert lote.custo_total_insumos == 50.0  # 5 * 10.0
        assert material_movement_service.consultar_saldo(malte.id)["quantidade_atual"] == 95


def test_registrar_envase_nao_confirma_de_novo_se_ja_feito(app):
    with app.app_context():
        malte = _criar_material_com_estoque(nome="Malte Envase JaFeito", quantidade_inicial=100, custo_unitario=10.0)
        lote = _criar_lote(com_ingrediente=(malte, 5))
        resultante = _criar_material_resultante()

        ingredient_consumption_service.confirmar_consumo_ingredientes(lote.id)
        db.session.refresh(lote)
        primeira_baixa = lote.insumos_baixados_em

        svc.registrar_envase(lote.id, resultante.id, quantidade_litros=10)

        db.session.refresh(lote)
        assert lote.insumos_baixados_em == primeira_baixa  # não mudou
        # Sem segunda baixa — saldo só desconta uma vez
        assert material_movement_service.consultar_saldo(malte.id)["quantidade_atual"] == 95


# ── custo de industrialização ──

def test_calcular_custo_industrializacao_envase(app):
    with app.app_context():
        malte = _criar_material_com_estoque(nome="Malte Custo Envase", quantidade_inicial=100, custo_unitario=10.0)
        lote = _criar_lote(com_ingrediente=(malte, 10))  # custo total insumo = 100
        tampinha = _criar_material_com_estoque(nome="Tampinha Custo Envase", quantidade_inicial=100, custo_unitario=0.5)
        resultante = _criar_material_resultante(componentes=[(tampinha, 2)])

        resultado = svc.registrar_envase(lote.id, resultante.id, quantidade_litros=10)
        envase_id = resultado["envase"]["id"]

        custo = svc.calcular_custo_industrializacao_envase(envase_id)

        # custo_cerveja = (100 / 10 litros) * 10 litros = 100 (só este envase no lote)
        assert custo["custo_cerveja"] == 100.0
        # custo_componentes = 10 unidades * 2 tampinhas * 0.5 = 10
        assert custo["custo_componentes"] == 10.0
        assert custo["custo_total_industrializacao"] == 110.0


# ── ingredient_consumption_service (skill 26) ──

def test_calcular_custo_insumos_receita_e_puro(app):
    with app.app_context():
        malte = _criar_material_com_estoque(nome="Malte Preview", quantidade_inicial=100, custo_unitario=8.0)
        lote = _criar_lote(com_ingrediente=(malte, 5))

        resultado = ingredient_consumption_service.calcular_custo_insumos_receita(lote.recipe_id)

        assert resultado["custo_total_estimado"] == 40.0
        # Nada foi gravado — saldo intacto
        assert material_movement_service.consultar_saldo(malte.id)["quantidade_atual"] == 100
        # Pode rodar de novo sem efeito colateral
        resultado2 = ingredient_consumption_service.calcular_custo_insumos_receita(lote.recipe_id)
        assert resultado2["custo_total_estimado"] == 40.0


def test_confirmar_consumo_ingredientes_e_idempotente(app):
    with app.app_context():
        malte = _criar_material_com_estoque(nome="Malte Idempotente", quantidade_inicial=100, custo_unitario=8.0)
        lote = _criar_lote(com_ingrediente=(malte, 5))

        primeiro = ingredient_consumption_service.confirmar_consumo_ingredientes(lote.id)
        assert primeiro["ja_confirmado"] is False
        assert primeiro["custo_total_insumos"] == 40.0
        assert material_movement_service.consultar_saldo(malte.id)["quantidade_atual"] == 95

        segundo = ingredient_consumption_service.confirmar_consumo_ingredientes(lote.id)
        assert segundo["ja_confirmado"] is True
        # Saldo não muda na segunda chamada
        assert material_movement_service.consultar_saldo(malte.id)["quantidade_atual"] == 95


def test_confirmar_consumo_lote_inexistente_levanta_erro(app):
    with app.app_context():
        with pytest.raises(ingredient_consumption_service.LoteNaoEncontradoError):
            ingredient_consumption_service.confirmar_consumo_ingredientes(99999)


def test_confirmar_consumo_sem_receita_vinculada_levanta_erro(app):
    with app.app_context():
        lote = BrewSession(name="Lote Sem Receita", status="concluida")
        db.session.add(lote)
        db.session.commit()
        with pytest.raises(ingredient_consumption_service.ReceitaNaoVinculadaError):
            ingredient_consumption_service.confirmar_consumo_ingredientes(lote.id)


# ── telas de listagem (regressão) ──

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


def test_botao_confirmar_ingredientes_aparece_e_funciona(app, client):
    """Rota nova (skill 26, gatilho explícito) — POST real via
    test client, confirma baixa e reflete no detail.html depois."""
    _login_admin(app, client)
    with app.app_context():
        malte = _criar_material_com_estoque(nome="Malte Botao Confirmar", quantidade_inicial=100, custo_unitario=8.0)
        malte_id = malte.id
        lote = _criar_lote(com_ingrediente=(malte, 5))
        lote_id = lote.id

    resp = client.get(f"/brewstation/brew-sessions/{lote_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Confirmar Ingredientes" in resp.data

    resp = client.post(f"/brewstation/brew-sessions/{lote_id}/confirmar-ingredientes", follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        assert material_movement_service.consultar_saldo(malte_id)["quantidade_atual"] == 95

    resp = client.get(f"/brewstation/brew-sessions/{lote_id}", follow_redirects=True)
    assert b"Confirmado em" in resp.data


@pytest.mark.parametrize("rota", [
    "/brewstation/envases",
    "/brewstation/item-envases",
])
def test_telas_de_listagem_nao_estouram_erro(app, client, rota):
    _login_admin(app, client)
    resp = client.get(rota, follow_redirects=True)
    assert resp.status_code == 200
