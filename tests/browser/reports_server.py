"""Servidor descartável Playwright; SQLite exclusivo da execução."""
import os
from core.app_factory import create_app
from core.db import db
from model.core.user import User
from flask import jsonify, url_for

from core.config import TestingConfig
previous_uri = TestingConfig.SQLALCHEMY_DATABASE_URI
try:
    if os.environ.get('REPORTS_TEST_DB'):
        TestingConfig.SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.environ['REPORTS_TEST_DB']
    app = create_app(env='testing')
finally:
    TestingConfig.SQLALCHEMY_DATABASE_URI = previous_uri
with app.app_context():
    user = User(username='reports_test', email='reports-browser@test.local', nome='Teste',
                nome_completo='Teste de navegador', celular='11999999999', is_admin=True, is_active=True)
    user.set_password('test-only-password')
    db.session.add(user)
    db.session.commit()
    from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
    from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
    from addons.addon_estoque.root.model.material import Material
    from addons.addon_estoque.root.model.saldo import Saldo
    from addons.addon_estoque.root.model.origem import Origem
    from addons.addon_estoque.root.model.tipo_produto import TipoProduto
    from addons.addon_estoque.root.model.categoria import Categoria
    plant = BrewPlant(name='Planta de teste')
    category = Categoria(descricao='Categoria de teste', codigo='REPORTS-TEST')
    db.session.add_all([plant, category]); db.session.flush()
    material = Material(unidade_medida='kg',nome='Material de teste', sku='REPORTS-TEST', origem_id=Origem.query.first().id,
                        tipo_produto_id=TipoProduto.query.first().id, categoria_id=category.id)
    lot = BrewSession(name='Lote de teste', plant_id=plant.id, custo_total_insumos=42.13)
    db.session.add_all([material, lot]); db.session.flush()
    saldo = Saldo(material_id=material.id, quantidade_atual=25, custo_medio=6.5, valor_total_estoque=162.5)
    db.session.add(saldo); db.session.commit()
    from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
    recipe=MashRecipe(name='Receita real de teste',volume_planejado_litros=25,description='Cadastro usado na verificação da biblioteca')
    db.session.add(recipe);db.session.commit()
    from decimal import Decimal
    from services.core.organization_service import save_organization
    from addons.addon_estoque.root.model.organization_stock import OrganizationBalance
    save_organization({'code':'REPORTS','name':'Organização de teste'})
    balance=OrganizationBalance(organization_code='REPORTS',material_id=material.id,currency_code='BRL',quantity=Decimal('25'),stock_value=Decimal('162.5'))
    db.session.add(balance);db.session.commit()
    fixture = {'organization_code':'REPORTS','recipe_id':recipe.id, 'plant_id':plant.id, 'session_id':lot.id, 'saldo_id':saldo.id}


@app.get('/__reports_fixture')
def report_fixture():
    # Existe somente neste servidor descartável de testing, nunca no addon.
    return jsonify(**fixture, saldo_url=url_for('saldos.detail', id=fixture['saldo_id']),
                   session_url=url_for('plant_workspace.shell', plant_id=fixture['plant_id'],
                                       tab='sessions', session_id=fixture['session_id']))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5068, use_reloader=False, threaded=bool(os.environ.get('REPORTS_TEST_DB')))
