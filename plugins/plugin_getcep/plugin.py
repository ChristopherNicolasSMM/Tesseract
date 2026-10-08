from pathlib import Path
from flask import Blueprint, jsonify, url_for
from flask_login import login_required
from core.plugin_base import PluginBase
from plugins.plugin_getcep.provider import ViaCEP, LookupError
__module__ = 'PluginGetCEP'


class PluginGetCEP(PluginBase):
    def register_routes(self, app):
        provider = ViaCEP()
        app.extensions['getcep_provider'] = provider
        bp = Blueprint('getcep', __name__, url_prefix='/api/plugins/getcep',
                       static_folder=str(Path(__file__).parent / 'static'), static_url_path='/assets')

        @bp.get('/<cep>')
        @login_required
        def lookup(cep):
            try:
                return jsonify(success=True, address=provider.lookup(cep), source='ViaCEP')
            except ValueError as exc:
                return jsonify(success=False, error=str(exc)), 422
            except LookupError as exc:
                return jsonify(success=False, error=str(exc)), exc.status

        app.register_blueprint(bp)
        assets_bp = Blueprint('getcep_assets', __name__, url_prefix='/plugins/getcep',
                              static_folder=str(Path(__file__).parent / 'static'), static_url_path='/static')
        app.register_blueprint(assets_bp)
        @app.context_processor
        def assets():
            return {'getcep_script_url': url_for('getcep_assets.static', filename='getcep.js', v=self.version),
                    'getcep_lookup_url': url_for('getcep.lookup', cep='__CEP__')}
