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
    "/estoque/fornecedor-enderecos",
    "/estoque/transportadora-enderecos",
])
def test_telas_de_listagem_nao_estouram_erro(app, client, rota):
    _login_admin(app, client)
    resp = client.get(rota, follow_redirects=True)
    assert resp.status_code == 200


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
