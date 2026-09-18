"""
tests/test_precificacao_envase.py

Cobre precificacao_service.py: resolução de custo real (último
ItemPedidoCompra), fallback pro preço padrão por tipo de insumo
(malte/lupulo/levedura) e o caso "sem_preco" (nenhum dos dois) —
proposta-precificacao-envase.md.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
from addons.addon_estoque.root.model.fornecedor import Fornecedor
from addons.addon_estoque.root.model.origem import Origem, SEED_NOME_A_DEFINIR
from addons.addon_estoque.root.model.tipo_produto import TipoProduto, SEED_NOME_INSUMO
from addons.addon_estoque.root.model.categoria import Categoria
from addons.addon_estoque.root.services.pedido_compra_service import PedidoCompraService
from addons.addon_estoque.root.services.item_pedido_compra_service import ItemPedidoCompraService
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_ingredientes.model.malte import Malte
from addons.addon_brewstation.features.feature_ingredientes.model.preco_padrao_insumo import PrecoPadraoInsumo
from addons.addon_brewstation.features.feature_envase.services import precificacao_service
from addons.addon_brewstation.features.feature_envase.model.calculo_precificacao import CalculoPrecificacao
from addons.addon_brewstation.features.feature_envase.model.item_custo_ingrediente import ItemCustoIngrediente


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


def _ids_lookup_padrao(categoria_nome: str = "materia_prima") -> dict:
    origem = Origem.query.filter_by(nome=SEED_NOME_A_DEFINIR).first()
    tipo_produto = TipoProduto.query.filter_by(descricao=SEED_NOME_INSUMO).first()
    categoria = Categoria.query.filter_by(descricao=categoria_nome).first()
    if not categoria:
        categoria = Categoria(descricao=categoria_nome, codigo=categoria_nome.upper().replace(" ", "_"),
                               tipo_produto_id=tipo_produto.id)
        db.session.add(categoria)
        db.session.commit()
    return {"origem_id": origem.id, "tipo_produto_id": tipo_produto.id, "categoria_id": categoria.id}


def _criar_material(nome: str, **kwargs) -> Material:
    ids = _ids_lookup_padrao()
    material = Material(nome=nome, sku=nome.upper().replace(" ", "-"), unidade_medida="kg", **ids, **kwargs)
    db.session.add(material)
    db.session.commit()
    return material


def _criar_lote_com_ingrediente(material: Material, quantidade: float) -> BrewSession:
    receita = MashRecipe(name="Receita Teste", versao=1, origem_receita="Manual")
    db.session.add(receita)
    db.session.commit()

    db.session.add(RecipeIngredient(
        recipe_id=receita.id, descricao_origem=material.nome,
        material_id=material.id, quantidade=quantidade, status_resolucao="resolvido",
    ))
    db.session.commit()

    lote = BrewSession(name="Sessão Teste", recipe_id=receita.id, status="concluida")
    db.session.add(lote)
    db.session.commit()
    return lote


def _registrar_compra(material: Material, preco_unitario: float, data_pedido: str = "2026-08-01") -> None:
    fornecedor = Fornecedor(razao_social="Fornecedor Teste LTDA")
    db.session.add(fornecedor)
    db.session.commit()

    unidade = MaterialUnidade(material_id=material.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
    db.session.add(unidade)
    db.session.commit()

    pedido_result = PedidoCompraService().create({
        "fornecedor_id": fornecedor.id, "data_pedido": data_pedido,
    })
    assert pedido_result.success, pedido_result.error
    pedido = pedido_result.data

    item_result = ItemPedidoCompraService().create({
        "pedido_compra_id": pedido.id, "material_id": material.id, "material_unidade_id": unidade.id,
        "quantidade": 10.0, "preco_unitario": preco_unitario,
    })
    assert item_result.success, item_result.error


def test_resolve_custo_real_quando_ha_compra_registrada(app):
    with app.app_context():
        material = _criar_material("Malte Pilsen Precificacao")
        db.session.add(Malte(material_id=material.id))
        db.session.commit()

        _registrar_compra(material, preco_unitario=27.50)
        lote = _criar_lote_com_ingrediente(material, quantidade=5.0)

        resultado = precificacao_service.simular(
            lote_id=lote.id, envase_id=None,
            percentual_lucro=0, percentual_ipi=0, percentual_icms=0,
        )

        assert len(resultado["itens"]) == 1
        item = resultado["itens"][0]
        assert item["origem_preco"] == "real"
        assert item["preco_unitario_usado"] == 27.50
        assert item["custo_total"] == pytest.approx(27.50 * 5.0)
        assert resultado["custo_ingredientes_total"] == pytest.approx(27.50 * 5.0)


def test_resolve_preco_padrao_quando_nao_ha_compra_mas_e_malte(app):
    with app.app_context():
        material = _criar_material("Malte Sem Compra")
        db.session.add(Malte(material_id=material.id))
        db.session.commit()

        row = PrecoPadraoInsumo.query.filter_by(tipo_insumo="malte").first()
        if not row:
            row = PrecoPadraoInsumo(tipo_insumo="malte", valor_padrao=25.0, unidade="kg")
            db.session.add(row)
            db.session.commit()

        lote = _criar_lote_com_ingrediente(material, quantidade=3.0)

        resultado = precificacao_service.simular(
            lote_id=lote.id, envase_id=None,
            percentual_lucro=0, percentual_ipi=0, percentual_icms=0,
        )

        item = resultado["itens"][0]
        assert item["origem_preco"] == "padrao"
        assert item["preco_unitario_usado"] == row.valor_padrao


def test_sem_preco_quando_nao_e_insumo_conhecido_e_nunca_foi_comprado(app):
    with app.app_context():
        material = _criar_material("Material Genérico Sem Preço")
        # Não vira Malte/Lupulo/Levedura, não tem ItemPedidoCompra.
        lote = _criar_lote_com_ingrediente(material, quantidade=2.0)

        resultado = precificacao_service.simular(
            lote_id=lote.id, envase_id=None,
            percentual_lucro=0, percentual_ipi=0, percentual_icms=0,
        )

        item = resultado["itens"][0]
        assert item["origem_preco"] == "sem_preco"
        assert item["preco_unitario_usado"] == 0.0
        assert resultado["custo_ingredientes_total"] == 0.0


def test_lucro_ipi_icms_aplicados_sobre_o_total(app):
    with app.app_context():
        material = _criar_material("Malte Para Calculo Completo")
        db.session.add(Malte(material_id=material.id))
        db.session.commit()
        _registrar_compra(material, preco_unitario=10.0)
        lote = _criar_lote_com_ingrediente(material, quantidade=10.0)  # custo = 100.0

        resultado = precificacao_service.simular(
            lote_id=lote.id, envase_id=None,
            percentual_lucro=20, percentual_ipi=5, percentual_icms=10,
        )

        assert resultado["subtotal"] == pytest.approx(100.0)
        assert resultado["valor_lucro"] == pytest.approx(20.0)  # 20% de 100
        total_antes_impostos = 120.0
        assert resultado["valor_ipi"] == pytest.approx(total_antes_impostos * 0.05)
        assert resultado["valor_icms"] == pytest.approx(total_antes_impostos * 0.10)
        assert resultado["valor_total"] == pytest.approx(
            total_antes_impostos + resultado["valor_ipi"] + resultado["valor_icms"]
        )


def test_simular_nao_grava_nada_calcular_e_salvar_grava(app):
    with app.app_context():
        material = _criar_material("Malte Para Simular Vs Salvar")
        db.session.add(Malte(material_id=material.id))
        db.session.commit()
        _registrar_compra(material, preco_unitario=15.0)
        lote = _criar_lote_com_ingrediente(material, quantidade=1.0)

        precificacao_service.simular(
            lote_id=lote.id, envase_id=None,
            percentual_lucro=10, percentual_ipi=0, percentual_icms=0,
        )
        assert CalculoPrecificacao.query.count() == 0

        resultado = precificacao_service.calcular_e_salvar(
            lote_id=lote.id, envase_id=None,
            percentual_lucro=10, percentual_ipi=0, percentual_icms=0,
        )
        assert CalculoPrecificacao.query.count() == 1
        calculo = CalculoPrecificacao.query.get(resultado["id"])
        assert calculo.envase_id is None  # fluxo simula -> calcula -> cria envase
        assert ItemCustoIngrediente.query.filter_by(calculo_id=calculo.id).count() == 1


def test_vincular_envase_preenche_envase_id_depois(app):
    with app.app_context():
        from addons.addon_brewstation.features.feature_envase.model.envase import Envase

        material = _criar_material("Malte Para Vincular Envase")
        db.session.add(Malte(material_id=material.id))
        db.session.commit()
        _registrar_compra(material, preco_unitario=12.0)
        lote = _criar_lote_com_ingrediente(material, quantidade=1.0)

        resultado = precificacao_service.calcular_e_salvar(
            lote_id=lote.id, envase_id=None,
            percentual_lucro=0, percentual_ipi=0, percentual_icms=0,
        )

        envase = Envase(lote_id=lote.id, status="registrado")
        db.session.add(envase)
        db.session.commit()

        atualizado = precificacao_service.vincular_envase(resultado["id"], envase.id)
        assert atualizado["envase_id"] == envase.id
