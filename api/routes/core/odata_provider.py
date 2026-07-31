"""
api/routes/core/odata_provider.py

Fase 10, Patch 2 — servidor OData do próprio Tesseract, servindo
entidades marcadas com @odata_expose (annotations/__init__.py). Uso
principal: consumidores externos que apontam pra
`/api/odata-provider` como se fosse qualquer outro servidor OData —
o Designer em si usa o atalho em processo (core/odata_provider/
service.py, chamado direto por core/odata/connection_manager.py
quando ODataConnection.is_local), não estas rotas HTTP.

Rotas:
    GET   /api/odata-provider/$metadata.json
    GET   /api/odata-provider/<entity>?$top=&$skip=&$orderby=&$filter=
    PATCH /api/odata-provider/<entity>(<key>)

Mesmo mecanismo de autenticação/permissão de api/routes/core/
options_routes.py: sempre exige @login_required (nunca anônimo de
fora, mesmo para entidade "pública" — pública aqui significa "sem
permission_required extra além de estar logado no Tesseract", não
"aberta pra internet").
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from core.odata_provider import metadata as odata_metadata
from core.odata_provider.service import (
    query_local, patch_local, EntityNotExposedError, PermissionDeniedError,
)

odata_provider_bp = Blueprint("odata_provider", __name__, url_prefix="/api/odata-provider")


@odata_provider_bp.route("/$metadata.json", methods=["GET"])
@login_required
def get_metadata():
    return jsonify(odata_metadata.build_metadata_json())


@odata_provider_bp.route("/<entity>", methods=["GET"])
@login_required
def get_entity_collection(entity):
    params = {
        "$top": request.args.get("$top"),
        "$skip": request.args.get("$skip"),
        "$orderby": request.args.get("$orderby"),
        "$filter": request.args.get("$filter"),
    }
    try:
        result = query_local(entity, params, user=current_user)
    except EntityNotExposedError:
        return jsonify({"error": f"Entidade '{entity}' não exposta pelo provedor local."}), 404
    except PermissionDeniedError as exc:
        return jsonify({"error": f"Permissão necessária: {exc}."}), 403
    return jsonify(result)


@odata_provider_bp.route("/<entity>(<key>)", methods=["PATCH"])
@login_required
def patch_entity(entity, key):
    data = request.get_json(silent=True) or {}
    try:
        result = patch_local(entity, key, data, user=current_user)
    except EntityNotExposedError:
        return jsonify({"error": f"Entidade '{entity}' não exposta pelo provedor local."}), 404
    except PermissionDeniedError as exc:
        return jsonify({"error": f"Permissão necessária: {exc}."}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(result)
