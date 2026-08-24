"""
addons/addon_brewstation/features/feature_yeast_bank/controller/yeast_bank_painel.py

Painel integrado do Yeast Bank (skill 21, seção 0/3) — tela/ação de
navegação em lote sobre várias entidades, não um CRUD genérico do
CrudGen. Por isso é escrita à mão, mesmo padrão de
`yeast_bank_viability.py` (skill 04: `docs/technical/06-...` — página
que orquestra, não persiste nada por conta própria).

Todo dado é buscado pelo navegador via API REST já existente
(`/api/brewstation/...`) — este controller só renderiza a casca da
página e os endpoints que ela vai chamar (skill 17, "Bloco JSON").
"""
from flask import Blueprint, render_template
from flask_login import login_required

yeast_bank_painel_bp = Blueprint(
    "yeast_bank_painel", __name__, url_prefix="/brewstation/yeast-bank"
)


@yeast_bank_painel_bp.route("/painel", methods=["GET"])
@login_required
def painel():
    config = {
        "endpoints": {
            "strains": "/api/brewstation/yeast-strains",
            "bank_items": "/api/brewstation/yeast-bank-items",
            "bank_events": "/api/brewstation/yeast-bank-events",
            "cell_counts": "/api/brewstation/yeast-cell-count-histories",
        },
        "links": {
            "storage_devices": "/brewstation/yeast-storage-devices/",
            "bank_config": "/brewstation/yeast-bank-configs/",
            "new_event": "/brewstation/yeast-bank-events/",
        },
    }
    return render_template("feature_yeast_bank/painel.html", config=config)
