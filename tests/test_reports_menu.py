"""Menu por descoberta padrão, sem entrada legada ou cadastros internos."""
from flask import url_for
from core.db import db
from core.module_base import ModuleBase
from model.core.transaction import Transaction
from model.core.user import User
from addons.addon_reports.addon import AddonReports
from tests.test_reports_workspace import app, client


def test_menu_uses_default_discovery_and_registered_list_endpoint(app, client):
    assert AddonReports.get_transactions is ModuleBase.get_transactions
    with app.app_context():
        group=Transaction.query.filter_by(code='TX_GROUP_AUTO_REPORTS').one()
        item=Transaction.query.filter_by(code='TX_AUTO_REPORT_TEMPLATES').one()
        assert group.route is None and group.label=='Relatórios'
        assert item.parent_id==group.id and item.route=='/reports/'
        assert item.icon=='bi-file-earmark-text'
        assert item.permission_required=='report_templates.list'
        active=Transaction.query.filter_by(source_module='reports',is_active=True).all()
        assert {tx.code for tx in active}=={group.code,item.code}
        with app.test_request_context():assert url_for('report_templates.list')=='/reports/'
    html=client.get('/reports/').data.decode('utf-8')
    assert 'TX_GROUP_AUTO_REPORTS' in html
    assert html.count('href="/reports/"')==1


def test_sync_retires_owned_legacy_entry_idempotently_and_preserves_manual(app):
    with app.app_context():
        tx=Transaction(code='TX_REPORT_TEMPLATES',label='Legado',route='/reports/',source_module='manual',is_active=True)
        db.session.add(tx);db.session.commit()
        app.module_manager.sync_all_transactions()
        assert tx.is_active
        tx.source_module='reports';db.session.commit()
        app.module_manager.sync_all_transactions();app.module_manager.sync_all_transactions()
        db.session.refresh(tx);assert not tx.is_active
        assert Transaction.query.filter_by(code='TX_AUTO_REPORT_TEMPLATES').count()==1
        assert Transaction.query.filter_by(code='TX_GROUP_AUTO_REPORTS').count()==1


def test_workspace_keeps_list_permission(client,monkeypatch):
    monkeypatch.setattr(User,'has_permission',lambda self,name:False)
    assert client.get('/reports/').status_code==403
