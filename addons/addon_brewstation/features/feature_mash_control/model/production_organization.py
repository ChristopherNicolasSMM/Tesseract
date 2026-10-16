"""Vínculo e custo exato separados dos campos Float históricos."""
import json
from datetime import datetime, timezone
from sqlalchemy import event
from core.db import db


class ProductionOrganization(db.Model):
    __tablename__ = 'production_organization'
    __crudgen_immutable__ = True
    session_id = db.Column(db.Integer, db.ForeignKey('session.id', ondelete='RESTRICT'), primary_key=True)
    organization_code = db.Column(db.String(40), nullable=False)
    snapshot_json = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def snapshot(self):
        return json.loads(self.snapshot_json)


class ProductionConsumption(db.Model):
    __tablename__ = 'production_consumption'
    __crudgen_immutable__ = True
    session_id = db.Column(db.Integer, db.ForeignKey('session.id', ondelete='RESTRICT'), primary_key=True)
    snapshot_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def snapshot(self):
        return json.loads(self.snapshot_json)


def immutable(*args):
    raise ValueError('Vínculo e custo produtivo imutáveis; preserve o histórico.')


for model in (ProductionOrganization, ProductionConsumption):
    event.listen(model, 'before_update', immutable)
    event.listen(model, 'before_delete', immutable)


def protect_session(mapper, connection, target):
    from sqlalchemy import inspect, select
    from .brew_session import BrewSession
    state = inspect(target)
    row = connection.execute(select(ProductionOrganization.snapshot_json).where(
        ProductionOrganization.session_id == target.id)).scalar()
    if row:
        recipe = state.attrs.recipe_id.history
        if recipe.has_changes() and target.recipe_id != json.loads(row)['recipe_id']:
            raise ValueError('Receita do lote vinculada à organização é imutável.')
        if state.attrs.volume_real_litros.history.has_changes():
            from addons.addon_brewstation.features.feature_envase.model.envase import Envase
            snapshots = connection.execute(select(Envase.producao_snapshot).where(Envase.lote_id == target.id)).scalars()
            if any(value and value.get('version') == 2 for value in snapshots):
                raise ValueError('Volume real congelado após o primeiro envase organizacional.')


from .brew_session import BrewSession
event.listen(BrewSession, 'before_update', protect_session)
