"""
tests/test_mash_control_ingredient_resolution.py

Cobre feature_mash_control: MashRecipe estendida (origem_receita,
versao, unique name+versao), ingredient_resolution_service
(resolver_ingrediente, confirmar_mapeamento, criar_nova_versao).
"""
import pytest
from sqlalchemy.exc import IntegrityError

from core.app_factory import create_app
from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.ingredient_mapping import IngredientMapping
from addons.addon_brewstation.features.feature_mash_control.model.recipe_history import RecipeHistory
from addons.addon_brewstation.features.feature_mash_control.services import ingredient_resolution_service as svc
from addons.addon_brewstation.features.feature_mash_control.services import ingredient_sanitation_service as sanitation
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.categoria import Categoria
from addons.addon_estoque.root.model.origem import Origem, SEED_NOME_A_DEFINIR
from addons.addon_estoque.root.model.tipo_produto import TipoProduto, SEED_NOME_INSUMO


def _linha_saneamento(receita, **dados):
    linha = RecipeIngredient(
        recipe_id=receita.id, descricao_origem="Pale Malt 2-Row", quantidade=5,
        unidade_medida="kg", tipo_ingrediente="fermentavel", uso_detalhado="mash",
        cor_ebc=6, rendimento=78, tempo_adicao_min=30,
    )
    for nome, valor in dados.items():
        setattr(linha, nome, valor)
    db.session.add(linha)
    db.session.commit()
    return linha


def test_saneamento_local_preserva_demais_receitas_depara_e_estoque(app):
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    from addons.addon_estoque.root.model.saldo import Saldo
    from addons.addon_estoque.root.services import estoque_service
    with app.app_context():
        material = _criar_material()
        estoque_service.registrar_movimentacao(material.id, "entrada", 10, custo_unitario=2)
        receita = _criar_receita(origem="BrewFather")
        outra = _criar_receita(nome="Outra Receita", origem="BrewFather")
        linha = _linha_saneamento(receita)
        linha_outra = _linha_saneamento(outra)
        antes = linha.to_dict()
        outra_antes = linha_outra.to_dict()
        mapping = IngredientMapping(origem_receita="BrewFather", descricao_origem=linha.descricao_origem,
                                    material_id=99999)
        db.session.add(mapping)
        db.session.commit()
        receita_antes = receita.to_dict()
        ledger_antes = [m.to_dict() for m in Movimentacao.query.order_by(Movimentacao.id).all()]
        saldos_antes = [s.to_dict() for s in Saldo.query.order_by(Saldo.id).all()]
        materiais_antes = Material.query.count()
        resultado = sanitation.sanear_ingrediente(receita.id, linha.id, status_resolucao="resolvido",
                                                  material_id=material.id)
        assert resultado == {**antes, "material_id": material.id, "status_resolucao": "resolvido"}
        assert linha_outra.to_dict() == outra_antes
        assert receita.to_dict() == receita_antes
        assert mapping.material_id == 99999 and IngredientMapping.query.count() == 1
        assert Material.query.count() == materiais_antes
        assert [m.to_dict() for m in Movimentacao.query.order_by(Movimentacao.id).all()] == ledger_antes
        assert [s.to_dict() for s in Saldo.query.order_by(Saldo.id).all()] == saldos_antes


def test_saneamento_nao_consumir_limpa_vinculo_e_repeticao_preserva_linha(app):
    with app.app_context():
        material = _criar_material()
        receita = _criar_receita()
        linha = _linha_saneamento(receita, material_id=material.id, status_resolucao="resolvido")
        primeira = sanitation.sanear_ingrediente(receita.id, linha.id, status_resolucao="ignorado")
        segunda = sanitation.sanear_ingrediente(receita.id, linha.id, status_resolucao="ignorado")
        assert primeira == segunda
        assert segunda["material_id"] is None and segunda["status_resolucao"] == "ignorado"
        sanitation.sanear_ingrediente(receita.id, linha.id, status_resolucao="resolvido", material_id=material.id)
        assert linha.material_id == material.id and linha.status_resolucao == "resolvido"


@pytest.mark.parametrize("contexto", ["outra_receita", "receita_apagada", "linha_apagada", "inexistente"])
def test_saneamento_rejeita_contexto_invalido(app, contexto):
    with app.app_context():
        receita = _criar_receita()
        linha = _linha_saneamento(receita)
        rid, iid = receita.id, linha.id
        if contexto == "outra_receita":
            rid = _criar_receita(nome="Outra").id
        elif contexto == "receita_apagada":
            receita.is_deleted = True
        elif contexto == "linha_apagada":
            linha.is_deleted = True
        else:
            iid = 99999
        db.session.commit()
        antes = linha.to_dict()
        with pytest.raises(sanitation.IngredienteNaoEncontradoError):
            sanitation.sanear_ingrediente(rid, iid, status_resolucao="ignorado")
        assert linha.to_dict() == antes


@pytest.mark.parametrize("estado,apagada", [("draft", False), ("active", False), ("paused", False),
                                           ("completed", False), ("aborted", False), ("completed", True)])
def test_saneamento_preserva_receita_vinculada_a_sessao_inclusive_lixeira(app, estado, apagada):
    from datetime import datetime, timezone
    with app.app_context():
        receita = _criar_receita()
        linha = _linha_saneamento(receita)
        sessao = BrewSession(name="Histórico protegido", recipe_id=receita.id, status=estado,
                             is_deleted=apagada, current_step_index=2,
                             custo_total_insumos=123 if estado == "completed" else None,
                             insumos_baixados_em=datetime.now(timezone.utc) if estado == "completed" else None,
                             notes="Não mudar", volume_real_litros=20)
        db.session.add(sessao)
        db.session.commit()
        antes, sessao_antes = linha.to_dict(), sessao.to_dict()
        with pytest.raises(sanitation.ReceitaEmUsoError):
            sanitation.sanear_ingrediente(receita.id, linha.id, status_resolucao="ignorado")
        assert linha.to_dict() == antes
        assert sessao.to_dict() == sessao_antes


@pytest.mark.parametrize("problema", ["inexistente", "apagado", "inativo", "id_booleano"])
def test_saneamento_rejeita_material_indisponivel(app, problema):
    with app.app_context():
        receita = _criar_receita()
        linha = _linha_saneamento(receita)
        material = _criar_material()
        if problema == "apagado":
            material.is_deleted = True
        elif problema == "inativo":
            material.ativo = False
        db.session.commit()
        mid = 99999 if problema == "inexistente" else (True if problema == "id_booleano" else material.id)
        with pytest.raises(ValueError):
            sanitation.sanear_ingrediente(receita.id, linha.id, status_resolucao="resolvido", material_id=mid)
        assert linha.material_id is None and linha.status_resolucao == "pendente_depara"


@pytest.mark.parametrize("status,mid", [("inventado", None), ("pendente_depara", None),
                                      ("resolvido", None), ("ignorado", 1)])
def test_saneamento_rejeita_decisao_incoerente(app, status, mid):
    with app.app_context():
        receita = _criar_receita()
        linha = _linha_saneamento(receita)
        with pytest.raises(ValueError):
            sanitation.sanear_ingrediente(receita.id, linha.id, status_resolucao=status, material_id=mid)
        assert linha.material_id is None and linha.status_resolucao == "pendente_depara"


def test_saneamento_vinculo_nao_encobre_pendencia_de_unidade(app):
    from addons.addon_brewstation.features.feature_mash_control.services.ingredient_consumption_service import conferir_ingredientes
    with app.app_context():
        receita = _criar_receita()
        linha = _linha_saneamento(receita, unidade_medida="PCT")
        material = _criar_material()
        sanitation.sanear_ingrediente(receita.id, linha.id, status_resolucao="resolvido", material_id=material.id)
        conferencia = conferir_ingredientes(receita.id)
        assert len(conferencia["pendencias"]) == 1
        assert linha.unidade_medida == "PCT" and linha.quantidade == 5


def test_saneamento_falha_de_commit_desfaz_alteracao(app, monkeypatch):
    with app.app_context():
        receita = _criar_receita()
        linha = _linha_saneamento(receita)
        material = _criar_material()
        ids = receita.id, linha.id, material.id
        def falhar():
            raise RuntimeError("Falha de gravação simulada")
        monkeypatch.setattr(db.session, "commit", falhar)
        with pytest.raises(RuntimeError):
            sanitation.sanear_ingrediente(ids[0], ids[1], status_resolucao="resolvido", material_id=ids[2])
        assert linha.material_id is None and linha.status_resolucao == "pendente_depara"


def test_saneamento_sem_commit_participa_do_rollback_do_chamador(app):
    with app.app_context():
        receita = _criar_receita()
        linha = _linha_saneamento(receita)
        material = _criar_material()
        sanitation.sanear_ingrediente(receita.id, linha.id, status_resolucao="resolvido",
                                      material_id=material.id, commit=False)
        assert linha.status_resolucao == "resolvido"
        db.session.rollback()
        assert linha.material_id is None and linha.status_resolucao == "pendente_depara"


@pytest.mark.parametrize("rid,iid", [(True, 1), (1, True), (0, 1), (1, -1), ("1", 1), (1, None)])
def test_saneamento_exige_ids_inteiros_positivos(app, rid, iid):
    with app.app_context():
        with pytest.raises(sanitation.IngredienteNaoEncontradoError):
            sanitation.sanear_ingrediente(rid, iid, status_resolucao="ignorado")


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


def _criar_receita(nome="Sangue de Druida", origem="Manual", versao=1):
    receita = MashRecipe(name=nome, versao=versao, origem_receita=origem)
    db.session.add(receita)
    db.session.commit()
    return receita


def _criar_material(nome="Malte Pilsen"):
    origem_lookup = Origem.query.filter_by(nome=SEED_NOME_A_DEFINIR).first()
    tipo_produto = TipoProduto.query.filter_by(descricao=SEED_NOME_INSUMO).first()
    categoria = Categoria.query.filter_by(descricao="materia_prima").first()
    if not categoria:
        categoria = Categoria(
            descricao="materia_prima", codigo="MATERIA_PRIMA",
            tipo_produto_id=tipo_produto.id,
        )
        db.session.add(categoria)
        db.session.flush()

    material = Material(
        nome=nome, sku=nome.upper().replace(" ", "-"), unidade_medida="kg",
        origem_id=origem_lookup.id, tipo_produto_id=tipo_produto.id, categoria_id=categoria.id,
    )
    db.session.add(material)
    db.session.commit()
    return material


def test_nome_versao_e_unico(app):
    with app.app_context():
        _criar_receita(nome="IPA Tropical", versao=1)
        duplicada = MashRecipe(name="IPA Tropical", versao=1, origem_receita="Manual")
        db.session.add(duplicada)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_mesma_receita_versoes_diferentes_e_permitido(app):
    with app.app_context():
        _criar_receita(nome="IPA Tropical", versao=1)
        v2 = MashRecipe(name="IPA Tropical", versao=2, origem_receita="Manual")
        db.session.add(v2)
        db.session.commit()
        assert v2.id is not None


def test_origem_receita_invalida_e_rejeitada_pelo_service(app):
    with app.app_context():
        receita = _criar_receita()
        with pytest.raises(svc.OrigemInvalidaError):
            svc.resolver_ingrediente(receita.id, "OutraCoisa", "Malte Pilsen 5kg")


def test_resolver_ingrediente_sem_mapeamento_fica_pendente(app):
    with app.app_context():
        receita = _criar_receita()
        resultado = svc.resolver_ingrediente(
            receita.id, "BrewFather", "Pale Malt 2-Row", quantidade=5, unidade_medida="kg",
        )
        assert resultado["status_resolucao"] == "pendente_depara"
        assert resultado["material_id"] is None


def test_resolver_ingrediente_com_mapeamento_existente_resolve_direto(app):
    with app.app_context():
        material = _criar_material()
        receita = _criar_receita()

        db.session.add(IngredientMapping(
            origem_receita="BrewFather", descricao_origem="Pale Malt 2-Row", material_id=material.id,
        ))
        db.session.commit()

        resultado = svc.resolver_ingrediente(
            receita.id, "BrewFather", "Pale Malt 2-Row", quantidade=5, unidade_medida="kg",
        )
        assert resultado["status_resolucao"] == "resolvido"
        assert resultado["material_id"] == material.id


def test_confirmar_mapeamento_resolve_pendentes_da_mesma_origem_descricao(app):
    with app.app_context():
        material = _criar_material()
        receita1 = _criar_receita(nome="Receita A", origem="BrewFather")
        receita2 = _criar_receita(nome="Receita B", origem="BrewFather")

        svc.resolver_ingrediente(receita1.id, "BrewFather", "Pale Malt 2-Row", quantidade=5)
        svc.resolver_ingrediente(receita2.id, "BrewFather", "Pale Malt 2-Row", quantidade=3)

        resultado = svc.confirmar_mapeamento("BrewFather", "Pale Malt 2-Row", material.id)

        assert resultado["ingredientes_resolvidos"] == 2
        pendentes_restantes = RecipeIngredient.query.filter_by(status_resolucao="pendente_depara").count()
        assert pendentes_restantes == 0


def test_confirmar_mapeamento_material_inexistente_levanta_erro(app):
    with app.app_context():
        with pytest.raises(ValueError):
            svc.confirmar_mapeamento("BrewFather", "Algo", 99999)


def test_criar_nova_versao_nao_altera_versao_anterior(app):
    with app.app_context():
        material = _criar_material()
        receita_v1 = _criar_receita(nome="Weiss Clássica", versao=1)
        svc.resolver_ingrediente(receita_v1.id, "Manual", "Trigo Maltado", quantidade=2)

        resultado = svc.criar_nova_versao(
            receita_v1.id, {"description": "ajuste de dry hop"}, observacao="Testando versionamento",
        )

        assert resultado["recipe"]["versao"] == 2
        assert resultado["recipe"]["name"] == "Weiss Clássica"
        assert resultado["recipe"]["description"] == "ajuste de dry hop"

        v1_recarregada = MashRecipe.query.filter_by(id=receita_v1.id).first()
        assert v1_recarregada.description != "ajuste de dry hop"


def test_criar_nova_versao_copia_ingredientes(app):
    with app.app_context():
        receita_v1 = _criar_receita(nome="Stout Imperial", versao=1)
        svc.resolver_ingrediente(receita_v1.id, "Manual", "Malte Chocolate", quantidade=1)
        svc.resolver_ingrediente(receita_v1.id, "Manual", "Lupulo Fuggle", quantidade=0.05)

        resultado = svc.criar_nova_versao(receita_v1.id, {})

        assert len(resultado["ingredientes"]) == 2
        nova_versao_id = resultado["recipe"]["id"]
        ingredientes_v2 = RecipeIngredient.query.filter_by(recipe_id=nova_versao_id).all()
        assert len(ingredientes_v2) == 2

        ingredientes_v1 = RecipeIngredient.query.filter_by(recipe_id=receita_v1.id).all()
        assert len(ingredientes_v1) == 2  # originais intactos


def test_criar_nova_versao_grava_snapshot_no_historico(app):
    with app.app_context():
        receita_v1 = _criar_receita(nome="Session IPA", versao=1)
        resultado = svc.criar_nova_versao(receita_v1.id, {}, observacao="Primeira revisão")

        historico = RecipeHistory.query.filter_by(recipe_id=resultado["recipe"]["id"]).first()
        assert historico is not None
        assert historico.observacao == "Primeira revisão"
        snapshot = historico.get_snapshot()
        assert snapshot["recipe"]["name"] == "Session IPA"
        assert snapshot["recipe"]["versao"] == 2


def test_criar_nova_versao_receita_inexistente_levanta_erro(app):
    with app.app_context():
        with pytest.raises(svc.ReceitaNaoEncontradaError):
            svc.criar_nova_versao(99999, {})


def test_criar_nova_versao_rejeita_campo_nao_editavel(app):
    with app.app_context():
        receita_v1 = _criar_receita()
        with pytest.raises(ValueError):
            svc.criar_nova_versao(receita_v1.id, {"versao": 99})


# ── Regressão: tela de detalhe (view/render real, não só status code) ──
# Bug real: template usava 'record.xxx' mas o controller gerado pelo
# CrudGen passa a variável como 'item' - só um teste que RENDERIZA a
# página (não apenas GET no manage/list) pega isso.

@pytest.fixture
def client(app):
    return app.test_client()


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


def test_tela_de_detalhe_da_receita_renderiza_sem_erro(app, client):
    with app.app_context():
        receita = _criar_receita(nome="Receita para Teste de Detalhe")
        svc.resolver_ingrediente(receita.id, "Manual", "Malte Pilsen", quantidade=5, etapa="mostura")
        recipe_id = receita.id

    _login_admin(app, client)
    resp = client.get(f"/brewstation/mash-recipes/{recipe_id}", follow_redirects=True)

    assert resp.status_code == 200
    corpo = resp.data.decode("utf-8")
    assert "Receita para Teste de Detalhe" in corpo
    assert "Malte Pilsen" in corpo


def _plano_completo_revision():
    from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep
    from addons.addon_brewstation.features.feature_mash_control.model.fermentation_step import FermentationStep
    from addons.addon_brewstation.features.feature_mash_control.model.water_profile import WaterProfile
    receita = _criar_receita(nome="Plano completo para revisão", origem="BrewFather")
    receita.volume_planejado_litros = 23.5
    receita.equipment_mapping = "Equipamento original"
    receita.origem_receita_id = "remote-123"
    ing = _linha_saneamento(receita, tipo_ingrediente="lupulo", etapa="fervura",
                           uso_detalhado="boil", alpha_acidos=12.4, atenuacao=75,
                           status_resolucao="ignorado", quantidade=0.05)
    boil = RecipeStep(recipe_id=receita.id, step_type="boil", nome="Fervura", ordem=2,
                      temperatura=100, tempo_min=60)
    db.session.add(boil)
    db.session.flush()
    alert = RecipeStep(recipe_id=receita.id, step_type="alert", nome="Lúpulo original", ordem=3,
                       parent_step_id=boil.id, source="auto_hop", source_recipe_ingredient_id=ing.id,
                       trigger_minutes_remaining=30)
    db.session.add_all([alert,
        RecipeStep(recipe_id=receita.id, step_type="mash", nome="Mostura", ordem=1,
                   temperatura=66.5, tempo_min=50, ramp_time_min=10, tipo="infusion"),
        RecipeStep(recipe_id=receita.id, step_type="mash", nome="Apagada", is_deleted=True),
        RecipeIngredient(recipe_id=receita.id, descricao_origem="Apagado", is_deleted=True),
        FermentationStep(recipe_id=receita.id, nome="Primária", temperatura=18.5, tempo_dias=8.5),
        FermentationStep(recipe_id=receita.id, nome="Apagada", is_deleted=True)])
    for index, context in enumerate(("source", "target", "mash", "sparge", "total")):
        db.session.add(WaterProfile(recipe_id=receita.id, contexto=context, calcio=10 + index,
                                   magnesio=3, sodio=4, cloreto=50, sulfato=80, bicarbonato=9, ph=5.4))
    db.session.commit()
    return receita, ing, boil, alert


def test_revisao_completa_remapeia_referencias_e_preserva_lote_custo_e_origem(app):
    from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
    with app.app_context():
        receita, ing, boil, alert = _plano_completo_revision()
        from datetime import datetime, timezone
        session = BrewSession(name="Lote histórico", recipe_id=receita.id, status="completed",
                              insumos_baixados_em=datetime.now(timezone.utc), custo_total_insumos=123.45)
        db.session.add(session)
        db.session.flush()
        session_step = BrewSessionStep(session_id=session.id, name="Executada", step_index=0,
                                       step_type="boil", source_recipe_step_id=boil.id, status="completed")
        db.session.add(session_step)
        db.session.commit()
        before = svc.build_recipe_snapshot(receita)
        session_before, step_before = session.to_dict(), session_step.to_dict()
        result = svc.criar_nova_versao(receita.id, {}, observacao="Revisão completa")
        new_id = result["recipe"]["id"]
        assert new_id != receita.id and result["recipe"]["versao"] == 2
        assert result["recipe"]["volume_planejado_litros"] == 23.5
        assert result["recipe"]["origem_receita_id"] == "remote-123"
        assert result["recipe"]["equipment_mapping"] == "Equipamento original"
        new_ing = result["ingredientes"][0]
        assert new_ing["id"] != ing.id and new_ing["recipe_id"] == new_id
        assert {k: v for k, v in new_ing.items() if k not in ("id", "recipe_id")} == {
            k: v for k, v in ing.to_dict().items() if k not in ("id", "recipe_id")}
        assert len(result["recipe_steps"]) == 3
        new_boil = next(row for row in result["recipe_steps"] if row["step_type"] == "boil")
        new_alert = next(row for row in result["recipe_steps"] if row["step_type"] == "alert")
        assert new_alert["parent_step_id"] == new_boil["id"] != boil.id
        assert new_alert["source_recipe_ingredient_id"] == new_ing["id"] != ing.id
        for key in ("fermentation_steps", "water_profiles"):
            assert [{k: v for k, v in row.items() if k not in ("id", "recipe_id")} for row in result[key]] == [
                {k: v for k, v in row.items() if k not in ("id", "recipe_id")} for row in before[key]]
        history = db.session.get(RecipeHistory, result["history_id"])
        assert history.get_snapshot()["source_recipe_id"] == receita.id
        assert history.get_snapshot()["recipe_steps"] == result["recipe_steps"]
        sanitation.editar_dados_ingrediente(new_id, new_ing["id"], {"quantidade": "0.07", "tempo_adicao_min": "15"})
        assert svc.build_recipe_snapshot(receita) == before
        assert session.to_dict() == session_before and session_step.to_dict() == step_before
        assert BrewSession.query.count() == 1


def test_revisar_versao_antiga_reserva_numero_apos_versoes_inclusive_apagadas(app):
    with app.app_context():
        recipe = _criar_receita(nome="Versões ramificadas")
        newer = _criar_receita(nome=recipe.name, versao=3)
        newer.is_deleted = True
        db.session.commit()
        assert svc.criar_nova_versao(recipe.id, {})["recipe"]["versao"] == 4


@pytest.mark.parametrize("broken", ["parent", "ingredient", "foreign_parent", "foreign_ingredient"])
def test_revisao_referencia_invalida_desfaz_copia_inteira(app, broken):
    with app.app_context():
        recipe, ing, boil, alert = _plano_completo_revision()
        if broken.startswith("foreign_"):
            other = _criar_receita(nome="Receita de outra referência")
            (boil if broken == "foreign_parent" else ing).recipe_id = other.id
        else:
            (boil if broken == "parent" else ing).is_deleted = True
        db.session.commit()
        before = MashRecipe.query.count(), RecipeHistory.query.count(), RecipeIngredient.query.count()
        with pytest.raises(ValueError):
            svc.criar_nova_versao(recipe.id, {})
        assert (MashRecipe.query.count(), RecipeHistory.query.count(), RecipeIngredient.query.count()) == before


@pytest.mark.parametrize("operation", ["revision", "edit"])
def test_revisao_e_edicao_falha_commit_rollback_inclui_alertas_e_historico(app, monkeypatch, operation):
    with app.app_context():
        recipe, ing, _, _ = _plano_completo_revision()
        before = svc.build_recipe_snapshot(recipe)
        count_recipes, count_history = MashRecipe.query.count(), RecipeHistory.query.count()
        def fail():
            raise RuntimeError("Falha na confirmação")
        monkeypatch.setattr(db.session, "commit", fail)
        with pytest.raises(RuntimeError):
            if operation == "revision":
                svc.criar_nova_versao(recipe.id, {})
            else:
                sanitation.editar_dados_ingrediente(recipe.id, ing.id, {"quantidade": 8, "tempo_adicao_min": 2})
        assert svc.build_recipe_snapshot(recipe) == before
        assert MashRecipe.query.count() == count_recipes and RecipeHistory.query.count() == count_history


def test_editar_dados_sincroniza_alertas_sem_tocar_manual_estoque_ou_vinculo(app):
    from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    from addons.addon_estoque.root.model.saldo import Saldo
    with app.app_context():
        receita, ing, boil, alert = _plano_completo_revision()
        manual = RecipeStep(recipe_id=receita.id, step_type="alert", nome="Manual", parent_step_id=boil.id,
                            trigger_minutes_remaining=5, source="manual")
        db.session.add(manual)
        db.session.commit()
        manual_before, ledger_before = manual.to_dict(), Movimentacao.query.count()
        balances_before = [row.to_dict() for row in Saldo.query.all()]
        sanitation.editar_dados_ingrediente(receita.id, ing.id, {"quantidade": "0,08", "tempo_adicao_min": "10"})
        assert alert.trigger_minutes_remaining == 10 and "0.08" in alert.nome
        assert ing.status_resolucao == "ignorado" and ing.material_id is None
        snapshot = RecipeHistory.query.filter_by(recipe_id=receita.id).order_by(RecipeHistory.id.desc()).first().get_snapshot()
        assert snapshot["ingredientes"][0]["quantidade"] == 0.08
        assert next(row for row in snapshot["recipe_steps"] if row["id"] == alert.id)["trigger_minutes_remaining"] == 10
        sanitation.editar_dados_ingrediente(receita.id, ing.id, {"etapa": "fermentacao"})
        assert alert.is_deleted and manual.to_dict() == manual_before
        assert Movimentacao.query.count() == ledger_before
        assert [row.to_dict() for row in Saldo.query.all()] == balances_before


@pytest.mark.parametrize("payload", [{"quantidade": "NaN"}, {"alpha_acidos": "inf"},
    {"quantidade": -1}, {"tempo_adicao_min": "1.5"}, {"tempo_adicao_min": "2147483648"},
    {"unidade_medida": "PCT de 1 kg"}, {"etapa": "inexistente"}, {"tipo_ingrediente": "inexistente"},
    {"uso_detalhado": "x" * 31}, {"material_id": 1}])
def test_editar_dados_rejeita_payload_sem_alteracao_parcial(app, payload):
    with app.app_context():
        recipe = _criar_receita()
        ing = _linha_saneamento(recipe)
        before = ing.to_dict()
        with pytest.raises(ValueError):
            sanitation.editar_dados_ingrediente(recipe.id, ing.id, payload)
        assert ing.to_dict() == before and RecipeHistory.query.count() == 0


@pytest.mark.parametrize("deleted", [False, True])
def test_editar_dados_receita_em_uso_bloqueia_inclusive_lixeira(app, deleted):
    with app.app_context():
        recipe = _criar_receita()
        ing = _linha_saneamento(recipe)
        db.session.add(BrewSession(name="Histórico", recipe_id=recipe.id, is_deleted=deleted))
        db.session.commit()
        with pytest.raises(sanitation.ReceitaEmUsoError):
            sanitation.editar_dados_ingrediente(recipe.id, ing.id, {"quantidade": 99})
        assert ing.quantidade == 5


@pytest.mark.parametrize("operation", ["revision", "edit"])
def test_revisao_edicao_commit_false_permite_rollback_externo(app, operation):
    with app.app_context():
        recipe, ing, _, _ = _plano_completo_revision()
        before = svc.build_recipe_snapshot(recipe)
        if operation == "revision":
            svc.criar_nova_versao(recipe.id, {}, commit=False)
        else:
            sanitation.editar_dados_ingrediente(recipe.id, ing.id, {"quantidade": 2}, commit=False)
        db.session.rollback()
        assert MashRecipe.query.count() == 1 and RecipeHistory.query.count() == 0
        assert svc.build_recipe_snapshot(recipe) == before


def test_edicao_unidade_catalogo_e_legado_sem_conversao_automatica(app):
    from addons.addon_estoque.root.model.unidade_catalogo import UnidadeCatalogo
    with app.app_context():
        if not UnidadeCatalogo.query.filter_by(codigo="PCT").first():
            db.session.add(UnidadeCatalogo(codigo="PCT", descricao="Pacote", dimensao="embalagem"))
            db.session.commit()
        recipe = _criar_receita()
        ing = _linha_saneamento(recipe, unidade_medida="unidade legada")
        sanitation.editar_dados_ingrediente(recipe.id, ing.id, {"quantidade": 6, "unidade_medida": "unidade legada"})
        assert ing.unidade_medida == "unidade legada"
        sanitation.editar_dados_ingrediente(recipe.id, ing.id, {"unidade_medida": "pct"})
        assert ing.unidade_medida == "PCT" and ing.quantidade == 6
        before = RecipeHistory.query.count()
        sanitation.editar_dados_ingrediente(recipe.id, ing.id, {"quantidade": 6})
        assert RecipeHistory.query.count() == before


def _conversion_material():
    from addons.addon_estoque.root.model.unidade_catalogo import UnidadeCatalogo
    material = _criar_material(nome="Whirlfloc conversão")
    material.unidade_medida = "UN"
    if not UnidadeCatalogo.query.filter_by(codigo="UN").first():
        db.session.add(UnidadeCatalogo(codigo="UN", descricao="Unidade", dimensao="contagem"))
    db.session.commit()
    return material


@pytest.mark.parametrize("source", ["item", "items", "ITEM", " ITEMS "])
def test_conversion_items_exige_fator_explicito_e_preserva_consumo_congelado(app, source):
    from addons.addon_estoque.root.services.material_conversion_service import cadastrar_conversao
    from addons.addon_brewstation.features.feature_envase.services.unidade_conversao import converter_quantidade
    from addons.addon_estoque.root.services import estoque_service
    from addons.addon_estoque.root.model.movimentacao import Movimentacao
    from addons.addon_brewstation.features.feature_mash_control.services.ingredient_consumption_service import confirmar_consumo_ingredientes
    with app.app_context():
        material = _conversion_material()
        assert converter_quantidade(2, source, "UN", material.id) == (2, False)
        cadastrar_conversao(material.id, source, "0,5", unidade_base_esperada="UN")
        assert converter_quantidade(2, source, "UN", material.id) == (1, True)
        estoque_service.registrar_movimentacao(material.id, "entrada", 10, custo_unitario=4)
        recipe = _criar_receita()
        _linha_saneamento(recipe, material_id=material.id, unidade_medida=source, quantidade=2, status_resolucao="resolvido")
        lot = BrewSession(name="Lote Whirlfloc", recipe_id=recipe.id, status="draft")
        db.session.add(lot)
        db.session.commit()
        first = confirmar_consumo_ingredientes(lot.id)
        count = Movimentacao.query.count()
        assert lot.custo_total_insumos == 4
        second = confirmar_consumo_ingredientes(lot.id)
        assert not first["ja_confirmado"] and second["ja_confirmado"]
        assert Movimentacao.query.count() == count
        assert lot.custo_total_insumos == 4
        assert lot.insumos_baixados_em is not None


def test_conversion_rollback_desfaz_catalogo_e_unidades_e_permite_nova_tentativa(app, monkeypatch):
    from addons.addon_estoque.root.services.material_conversion_service import cadastrar_conversao
    from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
    from addons.addon_estoque.root.model.unidade_catalogo import UnidadeCatalogo
    with app.app_context():
        material = _conversion_material()
        mid = material.id
        count = UnidadeCatalogo.query.count()
        commit = db.session.commit
        def fail():
            db.session.flush()
            raise RuntimeError("falha simulada após flush")
        monkeypatch.setattr(db.session, "commit", fail)
        with pytest.raises(RuntimeError):
            cadastrar_conversao(mid, "items", 1, unidade_base_esperada="UN")
        assert UnidadeCatalogo.query.count() == count
        assert MaterialUnidade.query.filter_by(material_id=mid).count() == 0
        monkeypatch.setattr(db.session, "commit", commit)
        cadastrar_conversao(mid, "items", 1, unidade_base_esperada="UN")
        assert MaterialUnidade.query.filter_by(material_id=mid).count() == 2


@pytest.mark.parametrize("case", ["inactive", "different", "duplicate", "deleted_catalog", "unknown"])
def test_conversion_conflitos_nao_sobrescrevem_cadastro(app, case):
    from addons.addon_estoque.root.services.material_conversion_service import cadastrar_conversao, obter_fator
    from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
    from addons.addon_estoque.root.model.unidade_catalogo import UnidadeCatalogo
    with app.app_context():
        material = _conversion_material()
        row = cadastrar_conversao(material.id, "items", 1, unidade_base_esperada="UN")
        conversion = db.session.get(MaterialUnidade, row["id"])
        factor = 1
        source = "items"
        if case == "inactive": conversion.ativo = False
        if case == "different": factor = 2
        if case == "duplicate": db.session.add(MaterialUnidade(material_id=material.id, unidade="items", fator_para_base=1))
        if case == "deleted_catalog": UnidadeCatalogo.query.filter_by(codigo="ITEM").first().is_deleted = True
        if case == "unknown": source = "misteriosa"
        db.session.commit()
        before = [r.to_dict() for r in MaterialUnidade.query.filter_by(material_id=material.id).all()]
        with pytest.raises(ValueError):
            cadastrar_conversao(material.id, source, factor, unidade_base_esperada="UN")
        assert [r.to_dict() for r in MaterialUnidade.query.filter_by(material_id=material.id).all()] == before
        if case in ("inactive", "duplicate"):
            assert obter_fator(material.id, "items", "UN") is None
