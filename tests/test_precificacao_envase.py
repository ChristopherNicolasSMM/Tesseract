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
from addons.addon_brewstation.features.feature_ingredientes.model.lupulo import Lupulo
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
    from addons.addon_estoque.root.services.estoque_service import receber_pedido_compra

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

    # Preço "real" (Saldo.custo_medio) só existe depois do recebimento
    # de fato — criar o pedido/item sozinho não basta (achado do
    # Christopher: o motor de precificação lê Saldo, não
    # ItemPedidoCompra direto, porque é ali que o valor já vem
    # convertido pra unidade-base do Material).
    update_result = PedidoCompraService().update(pedido.id, {"status": "confirmado"})
    assert update_result.success, update_result.error
    receber_pedido_compra(pedido.id)


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
        calculo = db.session.get(CalculoPrecificacao, resultado["id"])
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


def test_converte_grama_para_quilo_no_preco_padrao(app):
    """
    Achado do Christopher (print de tela): lúpulo cadastrado em gramas
    na receita, mas o preço padrão é por quilo — sem converter, 22 g
    virava "22" na conta e multiplicava por R$120/kg (R$2640 em vez
    de ~R$2,64).
    """
    with app.app_context():
        material = _criar_material("Lupulo Cascade Gramas")
        db.session.add(Lupulo(material_id=material.id))
        db.session.commit()

        row = PrecoPadraoInsumo.query.filter_by(tipo_insumo="lupulo").first()
        row.valor_padrao = 120.0
        row.unidade = "kg"
        db.session.commit()

        receita = MashRecipe(name="Receita Lupulo Gramas", versao=1, origem_receita="Manual")
        db.session.add(receita)
        db.session.commit()
        db.session.add(RecipeIngredient(
            recipe_id=receita.id, descricao_origem=material.nome,
            material_id=material.id, quantidade=22.0, unidade_medida="g",
            status_resolucao="resolvido",
        ))
        db.session.commit()
        lote = BrewSession(name="Sessão Lupulo Gramas", recipe_id=receita.id, status="concluida")
        db.session.add(lote)
        db.session.commit()

        resultado = precificacao_service.simular(
            lote_id=lote.id, envase_id=None,
            percentual_lucro=0, percentual_ipi=0, percentual_icms=0,
        )

        item = resultado["itens"][0]
        assert item["conversao_confiavel"] is True
        assert item["quantidade_convertida"] == pytest.approx(0.022)
        assert item["custo_total"] == pytest.approx(0.022 * 120.0)  # ~R$2,64, não R$2640
        assert resultado["custo_ingredientes_total"] == pytest.approx(2.64, abs=0.01)


def test_material_id_desconhecido_sem_unidade_cadastrada_marca_conversao_nao_confiavel(app):
    """Unidade que não é peso nem volume conhecido (ex.: 'un') e sem
    MaterialUnidade cadastrada -> não inventa fator, avisa."""
    with app.app_context():
        material = _criar_material("Insumo Unidade Exotica")
        db.session.add(Malte(material_id=material.id))
        db.session.commit()
        row = PrecoPadraoInsumo.query.filter_by(tipo_insumo="malte").first()
        row.unidade = "kg"
        db.session.commit()

        receita = MashRecipe(name="Receita Unidade Exotica", versao=1, origem_receita="Manual")
        db.session.add(receita)
        db.session.commit()
        db.session.add(RecipeIngredient(
            recipe_id=receita.id, descricao_origem=material.nome,
            material_id=material.id, quantidade=3.0, unidade_medida="sacola",
            status_resolucao="resolvido",
        ))
        db.session.commit()
        lote = BrewSession(name="Sessão Unidade Exotica", recipe_id=receita.id, status="concluida")
        db.session.add(lote)
        db.session.commit()

        resultado = precificacao_service.simular(
            lote_id=lote.id, envase_id=None,
            percentual_lucro=0, percentual_ipi=0, percentual_icms=0,
        )

        item = resultado["itens"][0]
        assert item["conversao_confiavel"] is False
        assert item["quantidade_convertida"] == 3.0  # não converteu, devolveu como veio


def test_material_unidade_cadastrada_tem_prioridade_sobre_conversao_generica(app):
    """Se o Material tem MaterialUnidade cadastrada pras duas unidades,
    usa o fator cadastrado (mais específico) em vez do genérico."""
    with app.app_context():
        material = _criar_material("Malte Saco Personalizado")
        db.session.add(Malte(material_id=material.id))
        db.session.commit()
        row = PrecoPadraoInsumo.query.filter_by(tipo_insumo="malte").first()
        row.valor_padrao = 100.0
        row.unidade = "kg"
        db.session.commit()

        # 1 "saco" cadastrado = 2 kg (fator customizado, não é o padrão métrico)
        db.session.add(MaterialUnidade(
            material_id=material.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True,
        ))
        db.session.add(MaterialUnidade(
            material_id=material.id, unidade="saco", fator_para_base=2.0, is_unidade_base=False,
        ))
        db.session.commit()

        receita = MashRecipe(name="Receita Saco Personalizado", versao=1, origem_receita="Manual")
        db.session.add(receita)
        db.session.commit()
        db.session.add(RecipeIngredient(
            recipe_id=receita.id, descricao_origem=material.nome,
            material_id=material.id, quantidade=3.0, unidade_medida="saco",
            status_resolucao="resolvido",
        ))
        db.session.commit()
        lote = BrewSession(name="Sessão Saco Personalizado", recipe_id=receita.id, status="concluida")
        db.session.add(lote)
        db.session.commit()

        resultado = precificacao_service.simular(
            lote_id=lote.id, envase_id=None,
            percentual_lucro=0, percentual_ipi=0, percentual_icms=0,
        )

        item = resultado["itens"][0]
        assert item["conversao_confiavel"] is True
        assert item["quantidade_convertida"] == pytest.approx(6.0)  # 3 sacos * 2kg
        assert item["custo_total"] == pytest.approx(600.0)


def test_material_nome_resolvido_em_vez_de_id_cru(app):
    """Achado do Christopher: a tela mostrava '#66' em vez do nome do Material."""
    with app.app_context():
        material = _criar_material("Malte Munich Nome Visivel")
        db.session.add(Malte(material_id=material.id))
        db.session.commit()
        lote = _criar_lote_com_ingrediente(material, quantidade=1.0)

        resultado = precificacao_service.simular(
            lote_id=lote.id, envase_id=None,
            percentual_lucro=0, percentual_ipi=0, percentual_icms=0,
        )

        item = resultado["itens"][0]
        assert item["material_nome"] == "Malte Munich Nome Visivel"


@pytest.mark.parametrize('recorded', [0.0, 50.0])
def test_precificacao_preserva_total_confirmado_sem_recalcular_receita(app, monkeypatch, recorded):
    from datetime import datetime, timezone
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    with app.app_context():
        material = _criar_material('Ingrediente congelado')
        lote = _criar_lote_com_ingrediente(material, 5)
        lote.insumos_baixados_em = datetime.now(timezone.utc)
        lote.custo_total_insumos = recorded
        db.session.commit()
        def fail(*args):
            raise AssertionError('Preço atual não pode substituir custo confirmado')
        monkeypatch.setattr(precificacao_service, '_resolver_custo_material', fail)
        before = Movimentacao.query.count()
        result = precificacao_service.simular(lote.id, None, 30, 0, 0)
        assert result['ingredientes_registrados'] and result['custo_ingredientes_total'] == recorded
        assert result['itens'] == [] and result['valor_total'] == recorded * 1.3
        saved = precificacao_service.calcular_e_salvar(lote.id, None, 30, 0, 0)
        assert db.session.get(CalculoPrecificacao, saved['id']).custo_ingredientes_total == recorded
        assert Movimentacao.query.count() == before and lote.custo_total_insumos == recorded


def test_precificacao_snapshot_prevalece_sobre_item_legado_e_preco_atual(app, monkeypatch):
    from datetime import datetime, timezone
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    from addons.addon_brewstation.features.feature_envase.model.item_envase import ItemEnvase
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    with app.app_context():
        material = _criar_material('Embalagem snapshot')
        lote = _criar_lote_com_ingrediente(material, 99)
        lote.insumos_baixados_em = datetime.now(timezone.utc)
        lote.custo_total_insumos = 50
        envase = Envase(lote_id=lote.id, quantidade_litros=2, componentes_snapshot=[{
            'material_componente_id': material.id, 'quantidade_total': 2, 'custo_medio': 3,
            'custo_linha': 6, 'movimentacao_id': 999}])
        db.session.add(envase); db.session.flush()
        db.session.add(ItemEnvase(envase_id=envase.id, material_id=material.id, quantidade=999))
        db.session.commit()
        def fail(*args): raise AssertionError('Não consultar preço atual')
        monkeypatch.setattr(precificacao_service, '_resolver_custo_material', fail)
        before = Movimentacao.query.count()
        result = precificacao_service.calcular_e_salvar(lote.id, envase.id, 0, 0, 0)
        assert result['embalagens_registradas'] and result['subtotal'] == 56
        assert result['itens'][0]['origem_preco'] == 'registrado'
        assert ItemCustoIngrediente.query.filter_by(calculo_id=result['id']).one().custo_total == 6
        assert Movimentacao.query.count() == before
        empty = Envase(lote_id=lote.id, componentes_snapshot=[])
        db.session.add(empty); db.session.commit()
        assert precificacao_service.simular(lote.id, empty.id, 0, 0, 0)['custo_embalagem_total'] == 0
        assert db.session.get(CalculoPrecificacao, result['id']).subtotal == 56


@pytest.mark.parametrize('state', ['foreign', 'cancelado', 'deleted', 'missing', 'deleted_lot'])
def test_precificacao_rejeita_envase_invalido_antes_de_salvar_ou_vincular(app, state):
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    with app.app_context():
        material = _criar_material('Ingrediente vínculo seguro')
        lote = _criar_lote_com_ingrediente(material, 5)
        saved = precificacao_service.calcular_e_salvar(lote.id, None, 0, 0, 0)
        other = BrewSession(name='Outro lote'); db.session.add(other); db.session.flush()
        envase = Envase(lote_id=other.id if state == 'foreign' else lote.id,
                        status='cancelado' if state == 'cancelado' else 'registrado',
                        is_deleted=state == 'deleted')
        db.session.add(envase); db.session.commit()
        if state == 'deleted_lot':
            lote.is_deleted = True; db.session.commit()
        eid = 999999 if state == 'missing' else envase.id
        for action in [precificacao_service.simular, precificacao_service.calcular_e_salvar]:
            with pytest.raises(ValueError): action(lote.id, eid, 0, 0, 0)
        with pytest.raises(ValueError): precificacao_service.vincular_envase(saved['id'], eid)
        assert CalculoPrecificacao.query.count() == 1
        assert db.session.get(CalculoPrecificacao, saved['id']).envase_id is None


def test_precificacao_confirmado_sem_custo_nao_fabrica_zero(app):
    from datetime import datetime, timezone
    with app.app_context():
        lote = BrewSession(name='Custo registrado ausente', insumos_baixados_em=datetime.now(timezone.utc))
        db.session.add(lote); db.session.commit()
        with pytest.raises(ValueError, match='sem custo registrado'):
            precificacao_service.calcular_e_salvar(lote.id, None, 0, 0, 0)
        assert CalculoPrecificacao.query.count() == 0


def test_precificacao_ignora_ingrediente_marcado_sem_consumo(app):
    with app.app_context():
        material = _criar_material('Ingrediente ignorado')
        lote = _criar_lote_com_ingrediente(material, 5)
        RecipeIngredient.query.filter_by(recipe_id=lote.recipe_id).one().status_resolucao = 'ignorado'
        db.session.commit()
        result = precificacao_service.simular(lote.id, None, 0, 0, 0)
        assert not result['ingredientes_registrados'] and result['itens'] == []
        assert result['subtotal'] == 0


@pytest.mark.parametrize('missing', ['custo_linha', 'custo_medio'])
def test_precificacao_snapshot_incompleto_nao_salva_zero_inventado(app, missing):
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    with app.app_context():
        lote = BrewSession(name='Snapshot incompleto'); db.session.add(lote); db.session.flush()
        component = {'material_componente_id': 1, 'quantidade_total': 2, 'custo_linha': 6, 'custo_medio': 3}
        component[missing] = None
        envase = Envase(lote_id=lote.id, componentes_snapshot=[component]); db.session.add(envase); db.session.commit()
        with pytest.raises(ValueError, match='sem custo registrado'):
            precificacao_service.calcular_e_salvar(lote.id, envase.id, 0, 0, 0)
        assert CalculoPrecificacao.query.count() == 0


def test_precificacao_legado_e_pendencias_sao_estimativas_explicitas(app, monkeypatch):
    from datetime import datetime, timezone
    from addons.addon_brewstation.features.feature_envase.model.envase import Envase
    from addons.addon_brewstation.features.feature_envase.model.item_envase import ItemEnvase
    with app.app_context():
        material = _criar_material('Embalagem legada')
        lote = _criar_lote_com_ingrediente(material, 5)
        ingredient = RecipeIngredient.query.filter_by(recipe_id=lote.recipe_id).one()
        ingredient.material_id = None
        db.session.commit()
        assert precificacao_service.simular(lote.id, None, 0, 0, 0)['estimativa_incompleta']
        lote.insumos_baixados_em = datetime.now(timezone.utc); lote.custo_total_insumos = 50
        envase = Envase(lote_id=lote.id)
        db.session.add(envase); db.session.flush()
        db.session.add(ItemEnvase(envase_id=envase.id, material_id=material.id, quantidade=2))
        db.session.commit()
        monkeypatch.setattr(precificacao_service, '_resolver_custo_material', lambda mid: (7, 'real', 'kg'))
        result = precificacao_service.simular(lote.id, envase.id, 0, 0, 0)
        assert result['ingredientes_registrados'] and not result['embalagens_registradas']
        assert result['custo_embalagem_total'] == 14 and result['subtotal'] == 64
