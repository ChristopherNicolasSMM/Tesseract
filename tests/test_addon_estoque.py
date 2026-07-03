"""
tests/test_addon_estoque.py

Cobre addon_estoque: Material/Composicao (CRUD basico + unicidade),
estoque_service.registrar_movimentacao (ledger + saldo, custo medio
ponderado, tipos entrada/saida/ajuste) e material_lookup (service
publico consumido por outros Addons).
"""
import pytest
from sqlalchemy.exc import IntegrityError

from core.app_factory import create_app
from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.composicao import Composicao
from addons.addon_estoque.root.model.saldo import Saldo
from addons.addon_estoque.root.services import estoque_service
from addons.addon_estoque.root.services import material_lookup


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


def _criar_material(nome="Malte Pilsen", categoria="materia_prima", **kwargs):
    material = Material(nome=nome, categoria=categoria, unidade_medida="kg", **kwargs)
    db.session.add(material)
    db.session.commit()
    return material


def test_cria_material_com_campos_basicos(app):
    with app.app_context():
        material = _criar_material(
            volume_calculado=1.5, unidade_medida_volume_calculado="l",
            volume_real=1.4, unidade_medida_volume_real="l",
            formato_fisico="saco",
        )
        assert material.id is not None
        assert material.ativo is True
        assert material.is_deleted is False
        assert material.volume_calculado == 1.5
        assert material.volume_real == 1.4


def test_nome_de_material_e_unico(app):
    with app.app_context():
        _criar_material(nome="Lupulo Cascade")
        duplicado = Material(nome="Lupulo Cascade", categoria="materia_prima")
        db.session.add(duplicado)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_composicao_liga_dois_materiais(app):
    with app.app_context():
        caixa = _criar_material(nome="Caixa de Garrafas", categoria="embalagem")
        garrafa = _criar_material(nome="Garrafa 600ml", categoria="embalagem")

        composicao = Composicao(material_pai_id=caixa.id, material_componente_id=garrafa.id, quantidade=24)
        db.session.add(composicao)
        db.session.commit()

        assert composicao.id is not None
        assert caixa.componentes[0].material_componente_id == garrafa.id
        assert garrafa.usado_em_composicoes[0].material_pai_id == caixa.id


def test_registrar_movimentacao_entrada_cria_saldo(app):
    with app.app_context():
        material = _criar_material()

        resultado = estoque_service.registrar_movimentacao(
            material.id, "entrada", 100, custo_unitario=5.0, lote_fornecedor="LOTE-001",
        )

        assert resultado["saldo"]["quantidade_atual"] == 100
        assert resultado["saldo"]["custo_medio"] == 5.0
        assert resultado["saldo"]["valor_total_estoque"] == 500.0
        assert resultado["movimentacao"]["tipo_movimentacao"] == "entrada"
        assert resultado["movimentacao"]["custo_total"] == 500.0


def test_entradas_sucessivas_calculam_custo_medio_ponderado(app):
    with app.app_context():
        material = _criar_material()

        estoque_service.registrar_movimentacao(material.id, "entrada", 100, custo_unitario=5.0)
        resultado = estoque_service.registrar_movimentacao(material.id, "entrada", 50, custo_unitario=8.0)

        # (100*5 + 50*8) / 150 = (500+400)/150 = 6.0
        assert resultado["saldo"]["quantidade_atual"] == 150
        assert resultado["saldo"]["custo_medio"] == 6.0


def test_saida_reduz_saldo_sem_alterar_custo_medio(app):
    with app.app_context():
        material = _criar_material()
        estoque_service.registrar_movimentacao(material.id, "entrada", 100, custo_unitario=5.0)

        resultado = estoque_service.registrar_movimentacao(material.id, "saida", 30)

        assert resultado["saldo"]["quantidade_atual"] == 70
        assert resultado["saldo"]["custo_medio"] == 5.0


def test_ajuste_negativo_reduz_saldo(app):
    with app.app_context():
        material = _criar_material()
        estoque_service.registrar_movimentacao(material.id, "entrada", 100, custo_unitario=5.0)

        resultado = estoque_service.registrar_movimentacao(material.id, "ajuste", -10)

        assert resultado["saldo"]["quantidade_atual"] == 90


def test_tipo_movimentacao_invalido_levanta_erro(app):
    with app.app_context():
        material = _criar_material()
        with pytest.raises(estoque_service.TipoMovimentacaoInvalidoError):
            estoque_service.registrar_movimentacao(material.id, "transferencia", 10)


def test_material_inexistente_levanta_erro(app):
    with app.app_context():
        with pytest.raises(estoque_service.MaterialNaoEncontradoError):
            estoque_service.registrar_movimentacao(99999, "entrada", 10, custo_unitario=1.0)


def test_saldo_status_abaixo_do_minimo(app):
    with app.app_context():
        material = _criar_material()
        estoque_service.registrar_movimentacao(material.id, "entrada", 5, custo_unitario=1.0)

        saldo_obj = Saldo.query.filter_by(material_id=material.id).first()
        saldo_obj.estoque_minimo = 10
        db.session.commit()

        assert saldo_obj.status == "abaixo_minimo"


def test_material_lookup_get_material(app):
    with app.app_context():
        material = _criar_material(nome="Levedura US-05")
        resultado = material_lookup.get_material(material.id)
        assert resultado["nome"] == "Levedura US-05"

        assert material_lookup.get_material(99999) is None
        assert material_lookup.get_material(None) is None


def test_material_lookup_get_material_by_nome(app):
    with app.app_context():
        _criar_material(nome="Lupulo Citra")
        resultado = material_lookup.get_material_by_nome("Lupulo Citra")
        assert resultado is not None
        assert material_lookup.get_material_by_nome("Nao Existe") is None


def test_material_lookup_busca_por_termo(app):
    with app.app_context():
        _criar_material(nome="Malte Pilsen")
        _criar_material(nome="Malte Munich")
        _criar_material(nome="Lupulo Cascade")

        resultados = material_lookup.buscar_material_por_termo("malte")
        nomes = {r["nome"] for r in resultados}

        assert nomes == {"Malte Pilsen", "Malte Munich"}
        assert material_lookup.buscar_material_por_termo("") == []
        assert material_lookup.buscar_material_por_termo(None) == []


def test_material_lookup_material_exists(app):
    with app.app_context():
        material = _criar_material()
        assert material_lookup.material_exists(material.id) is True
        assert material_lookup.material_exists(99999) is False
        assert material_lookup.material_exists(None) is False


def test_material_deletado_nao_e_encontrado_por_lookup(app):
    with app.app_context():
        material = _criar_material()
        material.is_deleted = True
        db.session.commit()

        assert material_lookup.get_material(material.id) is None
        assert material_lookup.material_exists(material.id) is False
