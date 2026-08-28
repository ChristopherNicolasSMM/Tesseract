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
from model.core.user import User
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.fabricante import Fabricante
from addons.addon_estoque.root.model.composicao import Composicao
from addons.addon_estoque.root.model.saldo import Saldo
from addons.addon_estoque.root.model.categoria import Categoria
from addons.addon_estoque.root.model.origem import Origem, SEED_NOME_A_DEFINIR
from addons.addon_estoque.root.model.tipo_produto import (
    TipoProduto,
    SEED_NOME_INSUMO,
    SEED_NOME_EMBALAGEM,
    SEED_NOME_PRODUTO_ACABADO,
    SEED_NOME_PECA,
    SEED_NOME_USO_E_CONSUMO,
)
from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
from addons.addon_estoque.root.model.fornecedor import Fornecedor
from addons.addon_estoque.root.model.transportadora import Transportadora
from addons.addon_estoque.root.model.endereco import Endereco
from addons.addon_estoque.root.model.fornecedor_endereco import FornecedorEndereco
from addons.addon_estoque.root.model.transportadora_endereco import TransportadoraEndereco
from addons.addon_estoque.root.services import estoque_service
from addons.addon_estoque.root.services import material_lookup


def _ids_lookup_padrao(categoria_nome: str = "materia_prima") -> dict:
    """
    Resolve origem_id/tipo_produto_id (seeds já criados no boot via
    ensure_default_estoque_lookups, ver core/app_factory.py) e
    categoria_id (get_or_create por descricao) — os 3 campos
    obrigatórios de Material que os testes desta suíte não testam
    diretamente.

    CORREÇÃO (skill 23, achado ao rodar a suíte antes da Fase 1):
    Categoria/TipoProduto usam `descricao`/`codigo` desde a sessão que
    substituiu o campo `nome` livre por FK — este helper ainda
    filtrava/criava por `nome` (atributo que não existe mais em
    nenhum dos dois models), quebrando toda criação de Material nos
    testes. `codigo` é gerado a partir do próprio nome da categoria
    (maiúsculo, sem espaço) só para satisfazer a coluna NOT NULL/
    unique — não é o gerador "de verdade" (isso é decisão de UI/
    service, fora do escopo desta correção).
    """
    origem = Origem.query.filter_by(nome=SEED_NOME_A_DEFINIR).first()
    tipo_produto = TipoProduto.query.filter_by(descricao=SEED_NOME_INSUMO).first()
    categoria = Categoria.query.filter_by(descricao=categoria_nome).first()
    if not categoria:
        categoria = Categoria(
            descricao=categoria_nome,
            codigo=categoria_nome.upper().replace(" ", "_"),
            tipo_produto_id=tipo_produto.id,
        )
        db.session.add(categoria)
        db.session.flush()
    return {
        "origem_id": origem.id,
        "tipo_produto_id": tipo_produto.id,
        "categoria_id": categoria.id,
    }


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _login_admin(app, client):
    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@test.local", nome="Admin",
                         nome_completo="Admin", celular="0", is_admin=True, is_active=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})


# ── Regressão: as 4 telas de listagem não podem estourar AttributeError ──
# (bug real reportado: is_deleted ausente em Composicao/Movimentacao/Saldo
# quebrava a tela "manage" gerada pelo CrudGen, que filtra por is_deleted
# incondicionalmente em toda entidade — skill 02, "padrão para qualquer
# entidade gerada pelo CrudGen")

@pytest.mark.parametrize("rota", [
    "/estoque/materials",
    "/estoque/composicaos",
    "/estoque/movimentacaos",
    "/estoque/saldos",
    "/estoque/material-unidades",
    "/estoque/fornecedores",
    "/estoque/transportadoras",
    "/estoque/enderecos",
    "/estoque/pedido-compras",
    "/estoque/processo-cotacaos",
])
def test_telas_de_listagem_nao_estouram_erro(app, client, rota):
    _login_admin(app, client)
    resp = client.get(rota, follow_redirects=True)
    assert resp.status_code == 200


# ── Fase 5 (skill 23) — grid de Endereços embutido em Fornecedor/Transportadora ──

def test_detalhe_fornecedor_renderiza_com_grid_de_enderecos(app, client):
    """
    Regressão-alvo desta fase: detail.html de Fornecedor ganhou a
    seção "Endereços" (grid desenhado à mão) - o teste parametrizado
    de listagem acima não cobre `/estoque/fornecedores/<id>`, só a
    lista. Erro de sintaxe Jinja no bloco novo (ex.: tag não fechada)
    só aparece renderizando o detalhe de verdade.
    """
    _login_admin(app, client)
    with app.app_context():
        fornecedor = _criar_fornecedor(razao_social="Fornecedor Detalhe LTDA")
        fornecedor_id = fornecedor.id

    resp = client.get(f"/estoque/fornecedores/{fornecedor_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Endere\xc3\xa7os" in resp.data  # "Endereços" em UTF-8
    assert b"estoque-endereco-embutido.js" in resp.data


def test_detalhe_transportadora_renderiza_com_grid_de_enderecos(app, client):
    _login_admin(app, client)
    with app.app_context():
        transportadora = Transportadora(nome="Transportadora Detalhe LTDA", tipo_frete="proprio")
        db.session.add(transportadora)
        db.session.commit()
        transportadora_id = transportadora.id

    resp = client.get(f"/estoque/transportadoras/{transportadora_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Endere\xc3\xa7os" in resp.data
    assert b"estoque-endereco-embutido.js" in resp.data


def test_api_fornecedor_enderecos_filtra_por_fornecedor_id(app, client):
    """Achado desta fase: list() sem filtro trazia a tabela inteira -
    a tela nova depende do filtro server-side pra não misturar
    endereços de fornecedores diferentes no mesmo grid."""
    _login_admin(app, client)
    with app.app_context():
        f1 = _criar_fornecedor(razao_social="Fornecedor A LTDA")
        f2 = _criar_fornecedor(razao_social="Fornecedor B LTDA")
        e1 = _criar_endereco(descricao="End A")
        e2 = _criar_endereco(descricao="End B")
        db.session.add_all([
            FornecedorEndereco(fornecedor_id=f1.id, endereco_id=e1.id, tipo_endereco="cobranca"),
            FornecedorEndereco(fornecedor_id=f2.id, endereco_id=e2.id, tipo_endereco="entrega"),
        ])
        db.session.commit()
        f1_id = f1.id

    resp = client.get(f"/api/estoque/fornecedor-enderecos/?fornecedor_id={f1_id}")
    assert resp.status_code == 200
    itens = resp.get_json()["items"]
    assert len(itens) == 1
    assert itens[0]["fornecedor_id"] == f1_id


def test_rotas_removidas_de_fornecedor_endereco_nao_existem_mais(app, client):
    """As telas antigas foram removidas de vez (decisão da sessão) -
    a rota web não deve existir mais (404), só a API REST."""
    _login_admin(app, client)
    resp = client.get("/estoque/fornecedor-enderecos", follow_redirects=True)
    assert resp.status_code == 404


def _criar_material(nome="Malte Pilsen", categoria="materia_prima", **kwargs):
    ids = _ids_lookup_padrao(categoria)
    sku = kwargs.pop("sku", None) or nome.upper().replace(" ", "-")
    material = Material(nome=nome, sku=sku, unidade_medida="kg", **ids, **kwargs)
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
        ids = _ids_lookup_padrao()
        duplicado = Material(nome="Lupulo Cascade", sku="LUPULO-CASCADE-2", **ids)
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


# ── Fase 1 (skill 23) — taxonomia TipoProduto x Categoria ──

def test_seeds_de_tipo_produto_cobrem_toda_a_taxonomia(app):
    with app.app_context():
        descricoes = {t.descricao for t in TipoProduto.query.all()}
        assert descricoes == {
            SEED_NOME_INSUMO,
            SEED_NOME_EMBALAGEM,
            SEED_NOME_PRODUTO_ACABADO,
            SEED_NOME_PECA,
            SEED_NOME_USO_E_CONSUMO,
        }
        # idempotente - nenhum duplicado nem codigo vazio
        for tipo in TipoProduto.query.all():
            assert tipo.codigo


def test_categoria_aceita_tipo_produto_id_opcional(app):
    with app.app_context():
        tipo_embalagem = TipoProduto.query.filter_by(descricao=SEED_NOME_EMBALAGEM).first()

        com_tipo = Categoria(descricao="Garrafa", codigo="GARRAFA", tipo_produto_id=tipo_embalagem.id)
        sem_tipo = Categoria(descricao="Diversos", codigo="DIVERSOS")
        db.session.add_all([com_tipo, sem_tipo])
        db.session.commit()

        assert com_tipo.tipo_produto_id == tipo_embalagem.id
        assert com_tipo.tipo_produto.descricao == SEED_NOME_EMBALAGEM
        assert sem_tipo.tipo_produto_id is None


# ── Fase 2 (skill 23) — fracionamento (MaterialUnidade) ──

def _criar_unidade(material, unidade, fator, is_base=False, **kwargs):
    obj = MaterialUnidade(
        material_id=material.id, unidade=unidade, fator_para_base=fator,
        is_unidade_base=is_base, **kwargs,
    )
    db.session.add(obj)
    db.session.commit()
    return obj


def test_material_unidade_permite_unidade_base_e_alternativa(app):
    with app.app_context():
        material = _criar_material(nome="Malte Pilsen Fracionado")

        base = _criar_unidade(material, "kg", 1.0, is_base=True)
        saco = _criar_unidade(material, "saco25kg", 25.0, is_base=False)

        assert base.is_unidade_base is True
        assert saco.fator_para_base == 25.0
        assert len(material.unidades) == 2


def test_material_unidade_rejeita_duas_unidades_base_para_o_mesmo_material(app):
    with app.app_context():
        material = _criar_material(nome="Lupulo Fracionado")
        _criar_unidade(material, "kg", 1.0, is_base=True)

        db.session.add(MaterialUnidade(
            material_id=material.id, unidade="g", fator_para_base=0.001, is_unidade_base=True,
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_material_unidade_mesmo_material_pode_ter_duas_unidades_nao_base(app):
    with app.app_context():
        material = _criar_material(nome="Levedura Fracionada")
        _criar_unidade(material, "g", 1.0, is_base=True)
        _criar_unidade(material, "pacote11g", 11.0, is_base=False)
        _criar_unidade(material, "pacote100g", 100.0, is_base=False)

        assert len(material.unidades) == 3


def test_material_unidade_tipo_uso_default_ambos(app):
    with app.app_context():
        material = _criar_material(nome="Agua Fracionada")
        unidade = _criar_unidade(material, "l", 1.0, is_base=True)
        assert unidade.tipo_uso == "ambos"


# ── Fase 3 (skill 23) — Fornecedor, Transportadora, Endereco ──

def _criar_endereco(**kwargs):
    defaults = {
        "logradouro": "Rua das Maltarias",
        "cidade": "Ribeirão Preto",
        "estado": "SP",
    }
    defaults.update(kwargs)
    obj = Endereco(**defaults)
    db.session.add(obj)
    db.session.commit()
    return obj


def test_criar_fornecedor_com_campos_basicos(app):
    with app.app_context():
        fornecedor = Fornecedor(razao_social="Malte & Cia LTDA", nome_fantasia="Malte & Cia")
        db.session.add(fornecedor)
        db.session.commit()

        assert fornecedor.id is not None
        assert fornecedor.ativo is True
        assert fornecedor.is_deleted is False


def test_criar_transportadora_com_tipo_frete(app):
    with app.app_context():
        transportadora = Transportadora(nome="Transportes Rápido LTDA", tipo_frete="terceirizado")
        db.session.add(transportadora)
        db.session.commit()

        assert transportadora.id is not None
        assert transportadora.tipo_frete == "terceirizado"


def test_endereco_e_dado_puro_sem_dono(app):
    with app.app_context():
        endereco = _criar_endereco(descricao="Depósito 2")
        assert endereco.id is not None
        assert endereco.pais == "Brasil"


def test_fornecedor_endereco_vincula_com_tipo_e_principal(app):
    with app.app_context():
        fornecedor = Fornecedor(razao_social="Lúpulos do Sul LTDA")
        db.session.add(fornecedor)
        endereco = _criar_endereco(logradouro="Av. dos Lúpulos, 100")
        db.session.commit()

        vinculo = FornecedorEndereco(
            fornecedor_id=fornecedor.id, endereco_id=endereco.id,
            tipo_endereco="cobranca", principal=True,
        )
        db.session.add(vinculo)
        db.session.commit()

        assert vinculo.tipo_endereco == "cobranca"
        assert vinculo.principal is True
        assert fornecedor.enderecos[0].endereco.cidade == "Ribeirão Preto"


def test_fornecedor_pode_ter_multiplos_enderecos_nao_principais(app):
    with app.app_context():
        fornecedor = Fornecedor(razao_social="Envases Brasil LTDA")
        db.session.add(fornecedor)
        e1 = _criar_endereco(descricao="Matriz")
        e2 = _criar_endereco(descricao="Filial")
        db.session.commit()

        db.session.add_all([
            FornecedorEndereco(fornecedor_id=fornecedor.id, endereco_id=e1.id, tipo_endereco="faturamento"),
            FornecedorEndereco(fornecedor_id=fornecedor.id, endereco_id=e2.id, tipo_endereco="entrega"),
        ])
        db.session.commit()

        assert len(fornecedor.enderecos) == 2


def test_fornecedor_endereco_rejeita_dois_principais(app):
    with app.app_context():
        fornecedor = Fornecedor(razao_social="Grãos & Grãos LTDA")
        db.session.add(fornecedor)
        e1 = _criar_endereco(descricao="Endereço A")
        e2 = _criar_endereco(descricao="Endereço B")
        db.session.commit()

        db.session.add(FornecedorEndereco(
            fornecedor_id=fornecedor.id, endereco_id=e1.id, tipo_endereco="cobranca", principal=True,
        ))
        db.session.commit()

        db.session.add(FornecedorEndereco(
            fornecedor_id=fornecedor.id, endereco_id=e2.id, tipo_endereco="entrega", principal=True,
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_transportadora_endereco_vincula_com_tipo(app):
    with app.app_context():
        transportadora = Transportadora(nome="Frete Rápido LTDA", tipo_frete="proprio")
        db.session.add(transportadora)
        endereco = _criar_endereco(descricao="Galpão")
        db.session.commit()

        vinculo = TransportadoraEndereco(
            transportadora_id=transportadora.id, endereco_id=endereco.id, tipo_endereco="correspondencia",
        )
        db.session.add(vinculo)
        db.session.commit()

        assert vinculo.tipo_endereco == "correspondencia"
        assert transportadora.enderecos[0].endereco.descricao == "Galpão"


def test_transportadora_endereco_rejeita_dois_principais(app):
    with app.app_context():
        transportadora = Transportadora(nome="Log Sul LTDA", tipo_frete="terceirizado")
        db.session.add(transportadora)
        e1 = _criar_endereco(descricao="End A")
        e2 = _criar_endereco(descricao="End B")
        db.session.commit()

        db.session.add(TransportadoraEndereco(
            transportadora_id=transportadora.id, endereco_id=e1.id, tipo_endereco="entrega", principal=True,
        ))
        db.session.commit()

        db.session.add(TransportadoraEndereco(
            transportadora_id=transportadora.id, endereco_id=e2.id, tipo_endereco="outro", principal=True,
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


# ── Fase 4 (skill 23) — PedidoCompra, ItemPedidoCompra, recebimento ──

import datetime as _dt

from addons.addon_estoque.root.services.pedido_compra_service import PedidoCompraService
from addons.addon_estoque.root.services.item_pedido_compra_service import ItemPedidoCompraService


def _criar_fornecedor(**kwargs):
    defaults = {"razao_social": "Fornecedor Teste LTDA"}
    defaults.update(kwargs)
    obj = Fornecedor(**defaults)
    db.session.add(obj)
    db.session.commit()
    return obj


def _criar_pedido_compra(fornecedor=None, **kwargs):
    """Passa pelo PedidoCompraService (não instancia o model direto) —
    o número automático só é gerado no hook `pbo_apply_fields`, que só
    roda através do service.create()."""
    if fornecedor is None:
        fornecedor = _criar_fornecedor()
    data = {"fornecedor_id": fornecedor.id, "data_pedido": "2026-08-01"}
    data.update(kwargs)
    resultado = PedidoCompraService().create(data)
    assert resultado.success, resultado.error
    return resultado.data


def _criar_item_pedido_compra(pedido, material, unidade, **kwargs):
    """Idem — quantidade_convertida_base/subtotal só são calculados no
    hook `pai_apply_fields`, que só roda através do service.create()."""
    data = {
        "pedido_compra_id": pedido.id,
        "material_id": material.id,
        "material_unidade_id": unidade.id,
        "quantidade": 10.0,
        "preco_unitario": 5.0,
    }
    data.update(kwargs)
    resultado = ItemPedidoCompraService().create(data)
    assert resultado.success, resultado.error
    return resultado.data


def test_pedido_compra_gera_numero_automatico(app):
    with app.app_context():
        pedido = _criar_pedido_compra()
        assert pedido.numero is not None
        assert pedido.numero.startswith("PC-")
        assert pedido.status == "rascunho"


def test_pedido_compra_respeita_numero_informado(app):
    with app.app_context():
        pedido = _criar_pedido_compra(numero="PC-CUSTOM-001")
        assert pedido.numero == "PC-CUSTOM-001"


def test_item_pedido_compra_calcula_fator_e_conversao(app):
    with app.app_context():
        material = _criar_material(nome="Malte Pilsen Compra")
        unidade = MaterialUnidade(material_id=material.id, unidade="saco25kg", fator_para_base=25.0, is_unidade_base=False)
        db.session.add(unidade)
        db.session.commit()

        pedido = _criar_pedido_compra()
        item = _criar_item_pedido_compra(pedido, material, unidade, quantidade=4.0, preco_unitario=150.0)

        assert item.fator_conversao_aplicado == 25.0
        assert item.quantidade_convertida_base == 100.0  # 4 sacos * 25kg
        assert item.subtotal == 600.0  # 4 * 150


def test_item_pedido_compra_fator_snapshot_nao_muda_com_cadastro(app):
    with app.app_context():
        material = _criar_material(nome="Lupulo Compra")
        unidade = MaterialUnidade(material_id=material.id, unidade="pacote1kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add(unidade)
        db.session.commit()

        pedido = _criar_pedido_compra()
        item = _criar_item_pedido_compra(pedido, material, unidade, quantidade=2.0, preco_unitario=80.0)
        assert item.fator_conversao_aplicado == 1.0

        # Cadastro muda depois — item já salvo não deve mudar retroativamente
        unidade.fator_para_base = 2.0
        db.session.commit()

        db.session.refresh(item)
        assert item.fator_conversao_aplicado == 1.0


def test_receber_pedido_compra_gera_movimentacao_e_atualiza_saldo(app):
    with app.app_context():
        material = _criar_material(nome="Malte Recebimento")
        unidade = MaterialUnidade(material_id=material.id, unidade="saco25kg", fator_para_base=25.0, is_unidade_base=False)
        db.session.add(unidade)
        db.session.commit()

        fornecedor = _criar_fornecedor(razao_social="Malte & Cia LTDA")
        pedido = _criar_pedido_compra(fornecedor=fornecedor, status="confirmado")
        _criar_item_pedido_compra(pedido, material, unidade, quantidade=2.0, preco_unitario=50.0)

        resultado = estoque_service.receber_pedido_compra(pedido.id)

        assert resultado["pedido_compra"]["status"] == "recebido"
        assert len(resultado["movimentacoes"]) == 1

        mov = resultado["movimentacoes"][0]
        assert mov["tipo_movimentacao"] == "entrada"
        assert mov["quantidade"] == 50.0  # 2 sacos * 25kg
        assert mov["fornecedor_id"] == fornecedor.id
        assert mov["unidade_original"] == "saco25kg"
        assert mov["quantidade_original"] == 2.0
        assert mov["custo_unitario"] == 2.0  # 50.0 (preco/saco) / 25 (fator) = 2.0/kg

        saldo = estoque_service.consultar_saldo(material.id)
        assert saldo["quantidade_atual"] == 50.0
        assert saldo["ultimo_preco_compra"] == 2.0
        assert saldo["ultimo_fornecedor_id"] == fornecedor.id
        assert saldo["data_ultima_compra"] is not None


def test_receber_pedido_compra_rejeita_status_diferente_de_confirmado(app):
    with app.app_context():
        pedido = _criar_pedido_compra(status="rascunho")
        with pytest.raises(estoque_service.PedidoCompraStatusInvalidoError):
            estoque_service.receber_pedido_compra(pedido.id)


def test_receber_pedido_compra_rejeita_pedido_sem_itens(app):
    with app.app_context():
        pedido = _criar_pedido_compra(status="confirmado")
        with pytest.raises(ValueError):
            estoque_service.receber_pedido_compra(pedido.id)


def test_receber_pedido_compra_inexistente_levanta_erro(app):
    with app.app_context():
        with pytest.raises(estoque_service.PedidoCompraNaoEncontradoError):
            estoque_service.receber_pedido_compra(999999)


def test_receber_pedido_compra_com_multiplos_itens(app):
    with app.app_context():
        malte = _criar_material(nome="Malte Multi")
        lupulo = _criar_material(nome="Lupulo Multi")
        un_malte = MaterialUnidade(material_id=malte.id, unidade="saco25kg", fator_para_base=25.0, is_unidade_base=False)
        un_lupulo = MaterialUnidade(material_id=lupulo.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add_all([un_malte, un_lupulo])
        db.session.commit()

        pedido = _criar_pedido_compra(status="confirmado")
        _criar_item_pedido_compra(pedido, malte, un_malte, quantidade=1.0, preco_unitario=100.0)
        _criar_item_pedido_compra(pedido, lupulo, un_lupulo, quantidade=3.0, preco_unitario=40.0)

        resultado = estoque_service.receber_pedido_compra(pedido.id)
        assert len(resultado["movimentacoes"]) == 2

        assert estoque_service.consultar_saldo(malte.id)["quantidade_atual"] == 25.0
        assert estoque_service.consultar_saldo(lupulo.id)["quantidade_atual"] == 3.0


# ── Fase 5 (skill 23) — detalhe de Pedido de Compra com abas ──

def test_detalhe_pedido_compra_renderiza_com_abas(app, client):
    """Regressão-alvo: detail.html de PedidoCompra foi reescrito do
    zero (abas Cabeçalho/Parceiros/Itens) — só renderizando de verdade
    (não só a lista) pega erro de sintaxe Jinja."""
    _login_admin(app, client)
    with app.app_context():
        pedido = _criar_pedido_compra()
        pedido_id = pedido.id

    resp = client.get(f"/estoque/pedido-compras/{pedido_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Cabe\xc3\xa7alho" in resp.data
    assert b"Parceiros de Neg\xc3\xb3cio" in resp.data
    assert b"pedido_compra_detalhe-itens.js" in resp.data


def test_detalhe_pedido_compra_confirmado_mostra_botao_receber(app, client):
    _login_admin(app, client)
    with app.app_context():
        pedido = _criar_pedido_compra(status="confirmado")
        pedido_id = pedido.id

    resp = client.get(f"/estoque/pedido-compras/{pedido_id}", follow_redirects=True)
    assert b"Receber Pedido" in resp.data


def test_detalhe_pedido_compra_rascunho_nao_mostra_botao_receber(app, client):
    _login_admin(app, client)
    with app.app_context():
        pedido = _criar_pedido_compra(status="rascunho")
        pedido_id = pedido.id

    resp = client.get(f"/estoque/pedido-compras/{pedido_id}", follow_redirects=True)
    assert b"Receber Pedido" not in resp.data


def test_api_material_unidades_filtra_por_material_id(app):
    with app.app_context():
        m1 = _criar_material(nome="Malte Filtro Unidade")
        m2 = _criar_material(nome="Lupulo Filtro Unidade")
        u1 = MaterialUnidade(material_id=m1.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        u2 = MaterialUnidade(material_id=m2.id, unidade="g", fator_para_base=1.0, is_unidade_base=True)
        db.session.add_all([u1, u2])
        db.session.commit()

        from addons.addon_estoque.root.services.material_unidade_service import MaterialUnidadeService
        resultado = MaterialUnidadeService().list(material_id=m1.id)
        assert len(resultado) == 1
        assert resultado[0].material_id == m1.id


def test_rotas_removidas_de_item_pedido_compra_nao_existem_mais(app, client):
    _login_admin(app, client)
    resp = client.get("/estoque/item-pedido-compras", follow_redirects=True)
    assert resp.status_code == 404


# ── Fase 6.1 (skill 24) — ProcessoCotacao, Cotacao, ItemCotacao ──

from addons.addon_estoque.root.model.processo_cotacao import ProcessoCotacao
from addons.addon_estoque.root.model.cotacao import Cotacao
from addons.addon_estoque.root.model.item_cotacao import ItemCotacao
from addons.addon_estoque.root.services.processo_cotacao_service import ProcessoCotacaoService
from addons.addon_estoque.root.services.cotacao_service import CotacaoService
from addons.addon_estoque.root.services.item_cotacao_service import ItemCotacaoService
from addons.addon_estoque.root.services.item_processo_cotacao_service import ItemProcessoCotacaoService
from addons.addon_estoque.root.model.item_processo_cotacao import ItemProcessoCotacao


def _criar_processo_cotacao(**kwargs):
    """Passa pelo service (não instancia o model direto) — número
    automático só é gerado no hook, que só roda via service.create()."""
    data = {"descricao": "Cotação de teste", "data_abertura": "2026-08-01"}
    data.update(kwargs)
    resultado = ProcessoCotacaoService().create(data)
    assert resultado.success, resultado.error
    return resultado.data


def _criar_cotacao(processo, fornecedor=None, **kwargs):
    if fornecedor is None:
        fornecedor = _criar_fornecedor()
    data = {"processo_cotacao_id": processo.id, "fornecedor_id": fornecedor.id}
    data.update(kwargs)
    resultado = CotacaoService().create(data)
    assert resultado.success, resultado.error
    return resultado.data


def _criar_item_processo_cotacao(processo, material, unidade, **kwargs):
    """O item PEDIDO (Material+quantidade), definido uma vez no
    processo — correção pós-Fase 6.3 (skill 24)."""
    data = {
        "processo_cotacao_id": processo.id, "material_id": material.id,
        "material_unidade_id": unidade.id, "quantidade_desejada": 10.0,
    }
    data.update(kwargs)
    resultado = ItemProcessoCotacaoService().create(data)
    assert resultado.success, resultado.error
    return resultado.data


def _criar_item_cotacao(cotacao, item_processo_cotacao, **kwargs):
    """A RESPOSTA de preço de um fornecedor pra um item já pedido."""
    data = {
        "cotacao_id": cotacao.id, "item_processo_cotacao_id": item_processo_cotacao.id,
        "preco_unitario": 5.0,
    }
    data.update(kwargs)
    resultado = ItemCotacaoService().create(data)
    assert resultado.success, resultado.error
    return resultado.data


def test_processo_cotacao_gera_numero_automatico(app):
    with app.app_context():
        processo = _criar_processo_cotacao()
        assert processo.numero is not None
        assert processo.numero.startswith("COT-")
        assert processo.status == "aberto"


def test_cotacao_gera_numero_com_sufixo_do_processo(app):
    with app.app_context():
        processo = _criar_processo_cotacao()
        f1 = _criar_fornecedor(razao_social="Fornecedor Cotacao A LTDA")
        f2 = _criar_fornecedor(razao_social="Fornecedor Cotacao B LTDA")

        cot1 = _criar_cotacao(processo, fornecedor=f1)
        cot2 = _criar_cotacao(processo, fornecedor=f2)

        assert cot1.numero == f"{processo.numero}-A"
        assert cot2.numero == f"{processo.numero}-B"


def test_cotacao_rejeita_mesmo_fornecedor_duas_vezes_no_processo(app):
    with app.app_context():
        processo = _criar_processo_cotacao()
        fornecedor = _criar_fornecedor(razao_social="Fornecedor Duplicado LTDA")
        _criar_cotacao(processo, fornecedor=fornecedor)

        db.session.add(Cotacao(processo_cotacao_id=processo.id, fornecedor_id=fornecedor.id))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_item_cotacao_calcula_fator_e_subtotal(app):
    with app.app_context():
        processo = _criar_processo_cotacao()
        cotacao = _criar_cotacao(processo)
        material = _criar_material(nome="Malte Cotacao")
        unidade = MaterialUnidade(material_id=material.id, unidade="saco25kg", fator_para_base=25.0, is_unidade_base=False)
        db.session.add(unidade)
        db.session.commit()

        item_pedido = _criar_item_processo_cotacao(processo, material, unidade, quantidade_desejada=2.0)
        item = _criar_item_cotacao(cotacao, item_pedido, preco_unitario=150.0)

        assert item.fator_conversao_aplicado == 25.0
        assert item.quantidade_convertida_base == 50.0
        assert item.subtotal == 300.0
        assert item.selecionado_como_vencedor is False


def test_item_processo_cotacao_reaproveitado_por_varios_fornecedores(app):
    """Cenário central da correção pós-Fase 6.3: o item pedido
    (Material+quantidade) é definido UMA VEZ no processo — dois
    fornecedores diferentes respondem preço pro MESMO
    item_processo_cotacao_id, sem redigitar o Material."""
    with app.app_context():
        processo = _criar_processo_cotacao()
        material = _criar_material(nome="Lupulo Comparado")
        unidade = MaterialUnidade(material_id=material.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add(unidade)
        db.session.commit()

        item_pedido = _criar_item_processo_cotacao(processo, material, unidade, quantidade_desejada=5.0)

        f1 = _criar_fornecedor(razao_social="Lupulos A LTDA")
        f2 = _criar_fornecedor(razao_social="Lupulos B LTDA")
        cot1 = _criar_cotacao(processo, fornecedor=f1)
        cot2 = _criar_cotacao(processo, fornecedor=f2)

        item1 = _criar_item_cotacao(cot1, item_pedido, preco_unitario=40.0)
        item2 = _criar_item_cotacao(cot2, item_pedido, preco_unitario=35.0)

        assert item1.item_processo_cotacao_id == item_pedido.id
        assert item2.item_processo_cotacao_id == item_pedido.id
        assert item1.material_id == material.id
        assert item2.material_id == material.id
        assert item1.subtotal == 200.0
        assert item2.subtotal == 175.0  # fornecedor B mais barato


def test_item_cotacao_quantidade_ofertada_diferente_da_desejada(app):
    """Fornecedor não consegue atender a quantidade pedida - oferta
    menos, preço/subtotal usam a quantidade ofertada, não a desejada."""
    with app.app_context():
        processo = _criar_processo_cotacao()
        material = _criar_material(nome="Malte Oferta Parcial")
        unidade = MaterialUnidade(material_id=material.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add(unidade)
        db.session.commit()

        item_pedido = _criar_item_processo_cotacao(processo, material, unidade, quantidade_desejada=100.0)
        cotacao = _criar_cotacao(processo)

        item_sem_oferta = _criar_item_cotacao(cotacao, item_pedido, preco_unitario=10.0)
        assert item_sem_oferta.quantidade == 100.0  # usa a desejada
        assert item_sem_oferta.subtotal == 1000.0


def test_rotas_de_cotacao_e_item_cotacao_nao_tem_tela_propria(app, client):
    """Decisão da skill 24 (mesma da Fase 5): Cotacao/ItemCotacao não
    têm tela própria desde o início — só a API."""
    _login_admin(app, client)
    resp = client.get("/estoque/cotacaos", follow_redirects=True)
    assert resp.status_code == 404
    resp = client.get("/estoque/item-cotacaos", follow_redirects=True)
    assert resp.status_code == 404


def test_api_cotacao_funciona_mesmo_sem_tela(app, client):
    _login_admin(app, client)
    with app.app_context():
        processo = _criar_processo_cotacao()
        fornecedor = _criar_fornecedor(razao_social="Fornecedor API LTDA")
        processo_id, fornecedor_id = processo.id, fornecedor.id

    resp = client.post("/api/estoque/cotacaos/", json={
        "processo_cotacao_id": processo_id, "fornecedor_id": fornecedor_id,
    })
    assert resp.status_code == 201
    assert resp.get_json()["item"]["numero"].startswith("COT-")


# ── Fase 6.2 (skill 24) — seleção de vencedor na Comparação ──

def test_selecionar_item_cotacao_vencedor_marca_e_desmarca_concorrentes(app):
    """Cenário central da Fase 6.2 (agora via item_processo_cotacao_id,
    não mais por nome de Material): dois fornecedores respondem ao
    MESMO item pedido - selecionar um como vencedor desmarca
    automaticamente qualquer outro vencedor do mesmo item."""
    with app.app_context():
        processo = _criar_processo_cotacao()
        material = _criar_material(nome="Malte Vencedor")
        unidade = MaterialUnidade(material_id=material.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add(unidade)
        db.session.commit()

        item_pedido = _criar_item_processo_cotacao(processo, material, unidade)
        f1 = _criar_fornecedor(razao_social="Fornecedor Vencedor A LTDA")
        f2 = _criar_fornecedor(razao_social="Fornecedor Vencedor B LTDA")
        cot1 = _criar_cotacao(processo, fornecedor=f1)
        cot2 = _criar_cotacao(processo, fornecedor=f2)
        item1 = _criar_item_cotacao(cot1, item_pedido, preco_unitario=40.0)
        item2 = _criar_item_cotacao(cot2, item_pedido, preco_unitario=35.0)

        # Marca item1 vencedor primeiro (preço pior, só pra testar a troca)
        resultado1 = estoque_service.selecionar_item_cotacao_vencedor(item1.id)
        assert resultado1["item_cotacao"]["selecionado_como_vencedor"] is True
        db.session.refresh(item1)
        assert item1.selecionado_como_vencedor is True

        # Agora marca item2 (mais barato) - item1 deve ser desmarcado automaticamente
        resultado2 = estoque_service.selecionar_item_cotacao_vencedor(item2.id)
        assert resultado2["item_cotacao"]["selecionado_como_vencedor"] is True
        assert item1.id in resultado2["desmarcados"]

        db.session.refresh(item1)
        db.session.refresh(item2)
        assert item1.selecionado_como_vencedor is False
        assert item2.selecionado_como_vencedor is True


def test_selecionar_vencedor_nao_afeta_item_diferente(app):
    """Vencedor de um item pedido não deve mexer no vencedor de outro
    item, mesmo dentro do mesmo processo/fornecedor."""
    with app.app_context():
        processo = _criar_processo_cotacao()
        malte = _criar_material(nome="Malte Independente")
        lupulo = _criar_material(nome="Lupulo Independente")
        un_malte = MaterialUnidade(material_id=malte.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        un_lupulo = MaterialUnidade(material_id=lupulo.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add_all([un_malte, un_lupulo])
        db.session.commit()

        item_pedido_malte = _criar_item_processo_cotacao(processo, malte, un_malte)
        item_pedido_lupulo = _criar_item_processo_cotacao(processo, lupulo, un_lupulo)

        fornecedor = _criar_fornecedor(razao_social="Fornecedor Multi Material LTDA")
        cotacao = _criar_cotacao(processo, fornecedor=fornecedor)
        item_malte = _criar_item_cotacao(cotacao, item_pedido_malte, preco_unitario=10.0)
        item_lupulo = _criar_item_cotacao(cotacao, item_pedido_lupulo, preco_unitario=20.0)

        estoque_service.selecionar_item_cotacao_vencedor(item_malte.id)
        estoque_service.selecionar_item_cotacao_vencedor(item_lupulo.id)

        db.session.refresh(item_malte)
        db.session.refresh(item_lupulo)
        assert item_malte.selecionado_como_vencedor is True
        assert item_lupulo.selecionado_como_vencedor is True


def test_desmarcar_item_cotacao_vencedor(app):
    with app.app_context():
        processo = _criar_processo_cotacao()
        material = _criar_material(nome="Malte Desmarcar")
        unidade = MaterialUnidade(material_id=material.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add(unidade)
        db.session.commit()

        item_pedido = _criar_item_processo_cotacao(processo, material, unidade)
        cotacao = _criar_cotacao(processo)
        item = _criar_item_cotacao(cotacao, item_pedido)

        estoque_service.selecionar_item_cotacao_vencedor(item.id)
        db.session.refresh(item)
        assert item.selecionado_como_vencedor is True

        estoque_service.desmarcar_item_cotacao_vencedor(item.id)
        db.session.refresh(item)
        assert item.selecionado_como_vencedor is False


def test_selecionar_vencedor_item_inexistente_levanta_erro(app):
    with app.app_context():
        with pytest.raises(estoque_service.ItemCotacaoNaoEncontradoError):
            estoque_service.selecionar_item_cotacao_vencedor(999999)


def test_api_selecionar_vencedor_funciona_end_to_end(app, client):
    _login_admin(app, client)
    with app.app_context():
        processo = _criar_processo_cotacao()
        material = _criar_material(nome="Malte API Vencedor")
        unidade = MaterialUnidade(material_id=material.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add(unidade)
        db.session.commit()
        item_pedido = _criar_item_processo_cotacao(processo, material, unidade)
        cotacao = _criar_cotacao(processo)
        item = _criar_item_cotacao(cotacao, item_pedido)
        item_id = item.id

    resp = client.post(f"/api/estoque/item-cotacaos/{item_id}/selecionar-vencedor")
    assert resp.status_code == 200
    assert resp.get_json()["item_cotacao"]["selecionado_como_vencedor"] is True

    resp = client.post(f"/api/estoque/item-cotacaos/{item_id}/desmarcar-vencedor")
    assert resp.status_code == 200
    assert resp.get_json()["item_cotacao"]["selecionado_como_vencedor"] is False


def test_api_cotacoes_filtra_por_processo_cotacao_id(app, client):
    _login_admin(app, client)
    with app.app_context():
        p1 = _criar_processo_cotacao(descricao="Processo A")
        p2 = _criar_processo_cotacao(descricao="Processo B")
        _criar_cotacao(p1)
        _criar_cotacao(p2)
        p1_id = p1.id

    resp = client.get(f"/api/estoque/cotacaos/?processo_cotacao_id={p1_id}")
    assert resp.status_code == 200
    itens = resp.get_json()["items"]
    assert len(itens) == 1
    assert itens[0]["processo_cotacao_id"] == p1_id


def test_api_item_cotacoes_filtra_por_processo_cotacao_id(app, client):
    """Achado central da Fase 6.2: a Comparação precisa ver TODOS os
    itens de TODAS as Cotacoes do processo numa chamada só (join)."""
    _login_admin(app, client)
    with app.app_context():
        processo = _criar_processo_cotacao()
        material = _criar_material(nome="Malte Join Comparacao")
        unidade = MaterialUnidade(material_id=material.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add(unidade)
        db.session.commit()

        item_pedido = _criar_item_processo_cotacao(processo, material, unidade)
        f1 = _criar_fornecedor(razao_social="Fornecedor Join A LTDA")
        f2 = _criar_fornecedor(razao_social="Fornecedor Join B LTDA")
        cot1 = _criar_cotacao(processo, fornecedor=f1)
        cot2 = _criar_cotacao(processo, fornecedor=f2)
        _criar_item_cotacao(cot1, item_pedido, preco_unitario=10.0)
        _criar_item_cotacao(cot2, item_pedido, preco_unitario=12.0)
        processo_id = processo.id

    resp = client.get(f"/api/estoque/item-cotacaos/?processo_cotacao_id={processo_id}")
    assert resp.status_code == 200
    itens = resp.get_json()["items"]
    assert len(itens) == 2


def test_api_item_processo_cotacaos_filtra_por_processo_cotacao_id(app, client):
    _login_admin(app, client)
    with app.app_context():
        p1 = _criar_processo_cotacao(descricao="Processo Item A")
        p2 = _criar_processo_cotacao(descricao="Processo Item B")
        material = _criar_material(nome="Malte Filtro Item Processo")
        unidade = MaterialUnidade(material_id=material.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add(unidade)
        db.session.commit()
        _criar_item_processo_cotacao(p1, material, unidade)
        _criar_item_processo_cotacao(p2, material, unidade)
        p1_id = p1.id

    resp = client.get(f"/api/estoque/item-processo-cotacaos/?processo_cotacao_id={p1_id}")
    assert resp.status_code == 200
    itens = resp.get_json()["items"]
    assert len(itens) == 1
    assert itens[0]["processo_cotacao_id"] == p1_id


def test_detalhe_processo_cotacao_renderiza_com_abas(app, client):
    """Regressão-alvo: detail.html de ProcessoCotacao foi reescrito
    com abas (Cabeçalho/Cotações/Comparação) - só renderizando de
    verdade pega erro de sintaxe Jinja."""
    _login_admin(app, client)
    with app.app_context():
        processo = _criar_processo_cotacao()
        processo_id = processo.id

    resp = client.get(f"/estoque/processo-cotacaos/{processo_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Cotac\xc3\xb5es" in resp.data or b"Cota\xc3\xa7\xc3\xb5es" in resp.data
    assert b"Compara\xc3\xa7\xc3\xa3o" in resp.data
    assert b"processo_cotacao_detalhe.js" in resp.data


# ── Fase 6.3 (skill 24) — ação "Gerar Pedido" ──

def test_gerar_pedidos_de_cotacao_agrupa_por_fornecedor(app):
    """Cenário central: dois fornecedores diferentes venceram itens
    diferentes no mesmo processo - devem virar 2 PedidoCompra
    separados, um por fornecedor."""
    with app.app_context():
        processo = _criar_processo_cotacao()
        malte = _criar_material(nome="Malte Gerar Pedido")
        lupulo = _criar_material(nome="Lupulo Gerar Pedido")
        un_malte = MaterialUnidade(material_id=malte.id, unidade="saco25kg", fator_para_base=25.0, is_unidade_base=False)
        un_lupulo = MaterialUnidade(material_id=lupulo.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add_all([un_malte, un_lupulo])
        db.session.commit()

        item_pedido_malte = _criar_item_processo_cotacao(processo, malte, un_malte, quantidade_desejada=2.0)
        item_pedido_lupulo = _criar_item_processo_cotacao(processo, lupulo, un_lupulo, quantidade_desejada=3.0)

        f1 = _criar_fornecedor(razao_social="Fornecedor Gerar A LTDA")
        f2 = _criar_fornecedor(razao_social="Fornecedor Gerar B LTDA")
        cot1 = _criar_cotacao(processo, fornecedor=f1)
        cot2 = _criar_cotacao(processo, fornecedor=f2)

        item_malte = _criar_item_cotacao(cot1, item_pedido_malte, preco_unitario=150.0)
        item_lupulo = _criar_item_cotacao(cot2, item_pedido_lupulo, preco_unitario=40.0)

        estoque_service.selecionar_item_cotacao_vencedor(item_malte.id)
        estoque_service.selecionar_item_cotacao_vencedor(item_lupulo.id)

        resultado = estoque_service.gerar_pedidos_de_cotacao(processo.id)

        assert len(resultado["pedidos_gerados"]) == 2
        assert resultado["processo_cotacao"]["status"] == "finalizado"

        fornecedores_dos_pedidos = {p["fornecedor_id"] for p in resultado["pedidos_gerados"]}
        assert fornecedores_dos_pedidos == {f1.id, f2.id}

        for pedido_dict in resultado["pedidos_gerados"]:
            assert pedido_dict["status"] == "rascunho"
            assert pedido_dict["numero"].startswith("PC-")


def test_gerar_pedidos_de_cotacao_agrupa_mesmo_fornecedor_num_so_pedido(app):
    """Dois Materiais vencidos pelo MESMO fornecedor devem virar UM só
    PedidoCompra com 2 itens, não dois pedidos separados."""
    with app.app_context():
        processo = _criar_processo_cotacao()
        malte = _criar_material(nome="Malte Mesmo Fornecedor")
        lupulo = _criar_material(nome="Lupulo Mesmo Fornecedor")
        un_malte = MaterialUnidade(material_id=malte.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        un_lupulo = MaterialUnidade(material_id=lupulo.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add_all([un_malte, un_lupulo])
        db.session.commit()

        item_pedido_malte = _criar_item_processo_cotacao(processo, malte, un_malte, quantidade_desejada=5.0)
        item_pedido_lupulo = _criar_item_processo_cotacao(processo, lupulo, un_lupulo, quantidade_desejada=2.0)

        fornecedor = _criar_fornecedor(razao_social="Fornecedor Unico LTDA")
        cotacao = _criar_cotacao(processo, fornecedor=fornecedor)
        item_malte = _criar_item_cotacao(cotacao, item_pedido_malte, preco_unitario=10.0)
        item_lupulo = _criar_item_cotacao(cotacao, item_pedido_lupulo, preco_unitario=30.0)

        estoque_service.selecionar_item_cotacao_vencedor(item_malte.id)
        estoque_service.selecionar_item_cotacao_vencedor(item_lupulo.id)

        resultado = estoque_service.gerar_pedidos_de_cotacao(processo.id)

        assert len(resultado["pedidos_gerados"]) == 1
        pedido = PedidoCompraService().get_by_id(resultado["pedidos_gerados"][0]["id"])
        assert len(pedido.itens) == 2


def test_gerar_pedidos_de_cotacao_nao_duplica_se_chamado_duas_vezes(app):
    with app.app_context():
        processo = _criar_processo_cotacao()
        material = _criar_material(nome="Malte Nao Duplicar")
        unidade = MaterialUnidade(material_id=material.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add(unidade)
        db.session.commit()

        item_pedido = _criar_item_processo_cotacao(processo, material, unidade)
        cotacao = _criar_cotacao(processo)
        item = _criar_item_cotacao(cotacao, item_pedido)
        estoque_service.selecionar_item_cotacao_vencedor(item.id)

        resultado1 = estoque_service.gerar_pedidos_de_cotacao(processo.id)
        assert len(resultado1["pedidos_gerados"]) == 1

        # Chamar de novo sem novo vencedor pendente deve levantar erro
        # (nada a gerar), não duplicar o pedido.
        with pytest.raises(ValueError):
            estoque_service.gerar_pedidos_de_cotacao(processo.id)

        db.session.refresh(item)
        assert item.pedido_compra_item_id is not None


def test_gerar_pedidos_de_cotacao_sem_vencedores_levanta_erro(app):
    with app.app_context():
        processo = _criar_processo_cotacao()
        with pytest.raises(ValueError):
            estoque_service.gerar_pedidos_de_cotacao(processo.id)


def test_gerar_pedidos_de_cotacao_processo_inexistente_levanta_erro(app):
    with app.app_context():
        with pytest.raises(estoque_service.ProcessoCotacaoNaoEncontradoError):
            estoque_service.gerar_pedidos_de_cotacao(999999)


def test_item_ja_convertido_em_pedido_nao_pode_mudar_vencedor(app):
    with app.app_context():
        processo = _criar_processo_cotacao()
        material = _criar_material(nome="Malte Trava Vencedor")
        unidade = MaterialUnidade(material_id=material.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add(unidade)
        db.session.commit()

        item_pedido = _criar_item_processo_cotacao(processo, material, unidade)
        cotacao = _criar_cotacao(processo)
        item = _criar_item_cotacao(cotacao, item_pedido)
        estoque_service.selecionar_item_cotacao_vencedor(item.id)
        estoque_service.gerar_pedidos_de_cotacao(processo.id)

        with pytest.raises(ValueError):
            estoque_service.desmarcar_item_cotacao_vencedor(item.id)


def test_api_gerar_pedido_end_to_end(app, client):
    _login_admin(app, client)
    with app.app_context():
        processo = _criar_processo_cotacao()
        material = _criar_material(nome="Malte API Gerar Pedido")
        unidade = MaterialUnidade(material_id=material.id, unidade="kg", fator_para_base=1.0, is_unidade_base=True)
        db.session.add(unidade)
        db.session.commit()
        item_pedido = _criar_item_processo_cotacao(processo, material, unidade)
        cotacao = _criar_cotacao(processo)
        item = _criar_item_cotacao(cotacao, item_pedido)
        estoque_service.selecionar_item_cotacao_vencedor(item.id)
        processo_id = processo.id

    resp = client.post(f"/estoque/processo-cotacaos/{processo_id}/gerar-pedido", follow_redirects=True)
    assert resp.status_code == 200
    assert b"pedido" in resp.data.lower()


# ── Correção pós-Fase 6.3 — @display_field/@weak_ref/post_create_redirect ──

def test_api_options_fornecedores_funciona(app, client):
    """Achado real: Fornecedor nunca teve @display_field -
    /api/options/fornecedores devolvia 400 antes da correção."""
    _login_admin(app, client)
    with app.app_context():
        _criar_fornecedor(razao_social="Fornecedor Options LTDA")

    resp = client.get("/api/options/fornecedores?search=Options")
    assert resp.status_code == 200
    dado = resp.get_json()
    assert len(dado["results"]) == 1
    assert "Options" in dado["results"][0]["text"]


def test_api_options_transportadoras_funciona(app, client):
    _login_admin(app, client)
    with app.app_context():
        db.session.add(Transportadora(nome="Transportadora Options LTDA", tipo_frete="proprio"))
        db.session.commit()

    resp = client.get("/api/options/transportadoras?search=Options")
    assert resp.status_code == 200
    assert len(resp.get_json()["results"]) == 1


def test_api_options_enderecos_funciona(app, client):
    _login_admin(app, client)
    with app.app_context():
        _criar_endereco(logradouro="Rua Options, 100")

    resp = client.get("/api/options/enderecos?search=Options")
    assert resp.status_code == 200
    assert len(resp.get_json()["results"]) == 1


def test_api_options_material_unidades_funciona(app, client):
    _login_admin(app, client)
    with app.app_context():
        material = _criar_material(nome="Material Options Unidade")
        db.session.add(MaterialUnidade(material_id=material.id, unidade="saco-options", fator_para_base=1.0, is_unidade_base=True))
        db.session.commit()

    resp = client.get("/api/options/material_unidades?search=options")
    assert resp.status_code == 200
    assert len(resp.get_json()["results"]) == 1


def test_form_criacao_pedido_compra_mostra_combo_de_fornecedor(app, client):
    """Regressão-alvo do achado do Christopher: a tela de criação
    (manage.html) deve renderizar o combo de busca, não um <input
    type="number"> pedindo o id cru."""
    _login_admin(app, client)
    resp = client.get("/estoque/pedido-compras", follow_redirects=True)
    assert resp.status_code == 200
    assert b'data-weakref-source="fornecedores"' in resp.data
    assert b'data-weakref-source="transportadoras"' in resp.data


def test_form_criacao_cotacao_via_processo_mostra_combo_de_fornecedor(app, client):
    _login_admin(app, client)
    with app.app_context():
        processo = _criar_processo_cotacao()
        processo_id = processo.id
    resp = client.get(f"/estoque/processo-cotacaos/{processo_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert b'data-weakref-source="fornecedores"' in resp.data


def test_criar_pedido_compra_redireciona_para_detalhe(app, client):
    """post_create_redirect novo - antes caia na lista sem indicar
    onde adicionar itens."""
    _login_admin(app, client)
    with app.app_context():
        fornecedor = _criar_fornecedor(razao_social="Fornecedor Redirect LTDA")
        fornecedor_id = fornecedor.id

    resp = client.post("/estoque/pedido-compras/", data={
        "fornecedor_id": str(fornecedor_id), "data_pedido": "2026-08-01",
    })
    assert resp.status_code == 302
    assert "/estoque/pedido-compras/" in resp.headers["Location"]
    assert resp.headers["Location"].rstrip("/").endswith(tuple(str(n) for n in range(10)))  # termina em .../<id>


def test_criar_processo_cotacao_redireciona_para_detalhe(app, client):
    _login_admin(app, client)
    resp = client.post("/estoque/processo-cotacaos/", data={
        "descricao": "Processo Redirect", "data_abertura": "2026-08-01",
    })
    assert resp.status_code == 302
    assert "/estoque/processo-cotacaos/" in resp.headers["Location"]


def test_detalhe_pedido_compra_aba_parceiros_mostra_combo(app, client):
    """Segundo ponto do achado: sem @weak_ref, a aba Parceiros de
    Negócio (Fase 5) não renderizava NADA pros campos fornecedor_id/
    transportadora_id (condição sempre falsa)."""
    _login_admin(app, client)
    with app.app_context():
        pedido = _criar_pedido_compra()
        pedido_id = pedido.id

    resp = client.get(f"/estoque/pedido-compras/{pedido_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert b'data-weakref-source="fornecedores"' in resp.data
    assert b'data-weakref-source="transportadoras"' in resp.data


# ── Correção pós-Fase 6.3 (2ª rodada) — combos de Material/Categoria/MaterialUnidade ──

def test_api_options_fabricantes_transportadoras_funciona(app, client):
    """Achado real: Fabricante/Origem/TipoProduto/Categoria nunca
    tiveram @display_field - causa raiz original de Material nunca
    ter tido combo funcionando."""
    _login_admin(app, client)
    with app.app_context():
        db.session.add(Fabricante(nome="Fabricante Options Teste"))
        db.session.commit()

    resp = client.get("/api/options/fabricantes?search=Options")
    assert resp.status_code == 200
    assert len(resp.get_json()["results"]) == 1


def test_api_options_origems_tipo_produtos_categorias_funciona(app, client):
    _login_admin(app, client)
    resp = client.get("/api/options/origems?search=A definir")
    assert resp.status_code == 200
    assert len(resp.get_json()["results"]) >= 1

    resp = client.get("/api/options/tipo_produtos?search=Insumo")
    assert resp.status_code == 200
    assert len(resp.get_json()["results"]) >= 1

    with app.app_context():
        db.session.add(Categoria(descricao="Categoria Options Teste", codigo="CAT-OPT"))
        db.session.commit()
    resp = client.get("/api/options/categorias?search=Options")
    assert resp.status_code == 200
    assert len(resp.get_json()["results"]) == 1


def test_api_options_material_unidades_material_id_funciona(app, client):
    """Bug reportado pelo Christopher (print) - MaterialUnidade.material_id
    nunca teve @weak_ref, form de criação mostrava spinner numérico
    cru em vez de combo de busca."""
    _login_admin(app, client)
    resp = client.get("/api/options/materials?search=")
    assert resp.status_code == 200  # não é mais 400


def test_form_criacao_material_mostra_combos(app, client):
    """Regressão-alvo: tela de criação de Material (manage.html) tinha
    <input type=number> cru pros 4 campos de referência - agora deve
    ter os 4 combos de busca."""
    _login_admin(app, client)
    resp = client.get("/estoque/materials", follow_redirects=True)
    assert resp.status_code == 200
    assert b'data-weakref-source="fabricantes"' in resp.data
    assert b'data-weakref-source="origems"' in resp.data
    assert b'data-weakref-source="tipo_produtos"' in resp.data
    assert b'data-weakref-source="categorias"' in resp.data


def test_form_criacao_material_unidade_mostra_combo_de_material(app, client):
    """Bug reportado pelo Christopher (print 1) - tela de criação de
    Unidade de Material."""
    _login_admin(app, client)
    resp = client.get("/estoque/material-unidades", follow_redirects=True)
    assert resp.status_code == 200
    assert b'data-weakref-source="materials"' in resp.data
    assert b"estoque-unidades-padrao" in resp.data  # datalist de valores padrao


def test_detalhe_material_mostra_grid_de_unidades(app, client):
    """'para cadastrar material tem de associar a unidade' - grid
    embutido no detalhe de Material, mesmo padrao da Fase 5."""
    _login_admin(app, client)
    with app.app_context():
        material = _criar_material(nome="Material Grid Unidades")
        material_id = material.id

    resp = client.get(f"/estoque/materials/{material_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"material-unidades-embutido.js" in resp.data
    assert b'data-weakref-source="fabricantes"' in resp.data  # aba de edicao tambem corrigida


def test_criar_material_com_combos_funciona_end_to_end(app, client):
    """Fluxo completo: criar Fabricante/Origem/TipoProduto/Categoria,
    depois criar Material referenciando os 4 via POST direto (como o
    weak_ref_combo.js faria) - confirma que o service aceita e a
    tela de detalhe renderiza sem erro depois."""
    _login_admin(app, client)
    with app.app_context():
        fabricante = Fabricante(nome="Fabricante E2E LTDA")
        db.session.add(fabricante)
        origem = Origem.query.filter_by(nome=SEED_NOME_A_DEFINIR).first()
        tipo_produto = TipoProduto.query.filter_by(descricao=SEED_NOME_INSUMO).first()
        db.session.commit()
        categoria = Categoria(descricao="Categoria E2E", codigo="CAT-E2E", tipo_produto_id=tipo_produto.id)
        db.session.add(categoria)
        db.session.commit()
        fabricante_id, origem_id, tipo_produto_id, categoria_id = (
            fabricante.id, origem.id, tipo_produto.id, categoria.id,
        )

    resp = client.post("/estoque/materials/", data={
        "nome": "Material E2E Combos", "sku": "SKU-E2E-COMBOS",
        "fabricante_id": str(fabricante_id), "origem_id": str(origem_id),
        "tipo_produto_id": str(tipo_produto_id), "categoria_id": str(categoria_id),
    })
    assert resp.status_code == 302

    with app.app_context():
        material = Material.query.filter_by(sku="SKU-E2E-COMBOS").first()
        assert material is not None
        assert material.fabricante_id == fabricante_id
        material_id = material.id

    resp = client.get(f"/estoque/materials/{material_id}", follow_redirects=True)
    assert resp.status_code == 200


def test_categoria_com_tipo_produto_mostra_combo_no_detalhe(app, client):
    _login_admin(app, client)
    with app.app_context():
        tipo_produto = TipoProduto.query.filter_by(descricao=SEED_NOME_EMBALAGEM).first()
        categoria = Categoria(descricao="Categoria Combo Teste", codigo="CAT-COMBO", tipo_produto_id=tipo_produto.id)
        db.session.add(categoria)
        db.session.commit()
        categoria_id = categoria.id

    resp = client.get(f"/estoque/categorias/{categoria_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert b'data-weakref-source="tipo_produtos"' in resp.data


def test_criar_material_com_erro_de_validacao_preserva_dados_digitados(app, client):
    """Achado real (mesma classe de bug ja documentado em
    fornecedores.py): create() fazia redirect() em erro, perdendo tudo
    que a pessoa tinha digitado - materials.py nunca tinha recebido
    essa correcao."""
    _login_admin(app, client)
    resp = client.post("/estoque/materials/", data={
        "nome": "Material Sem SKU Duplicado Teste",
        # sku ausente de proposito - deve falhar validacao (required)
    })
    assert resp.status_code == 200  # re-renderiza, nao redireciona
    assert b"Material Sem SKU Duplicado Teste" in resp.data
