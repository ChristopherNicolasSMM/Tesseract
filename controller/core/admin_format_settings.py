"""
controller/core/admin_format_settings.py

Tela de edição do padrão GLOBAL de formatação (moeda/data) — achado do
Christopher, sessão addon_estoque: "colocar nas configurações do
sistema... pra servir em todo o sistema". Mesmo padrão de
admin_menu_settings.py (tela simples de system_config, sem entidade
própria — só key/value).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.db import db
from core.permissions import permission_required
from core.formatting import (
    CHAVE_MOEDA_SIMBOLO, CHAVE_MOEDA_CASAS_DECIMAIS, CHAVE_DATA_FORMATO,
    PADRAO_MOEDA_SIMBOLO, PADRAO_MOEDA_CASAS_DECIMAIS, PADRAO_DATA_FORMATO,
    formatar_moeda, formatar_data,
)
from model.core.system_config import SystemConfig

admin_format_settings_bp = Blueprint("admin_format_settings", __name__, url_prefix="/admin/format-settings")

# Opções de formato de data oferecidas na tela — strftime real, não
# "dd/mm/yyyy" livre (evita a pessoa digitar um formato inválido que só
# quebra na hora de exibir).
_OPCOES_DATA_FORMATO = [
    ("%d/%m/%Y", "31/08/2026 (dd/mm/aaaa)"),
    ("%Y-%m-%d", "2026-08-31 (aaaa-mm-dd, ISO)"),
    ("%d/%m/%y", "31/08/26 (dd/mm/aa)"),
    ("%m/%d/%Y", "08/31/2026 (mm/dd/aaaa, EUA)"),
]


def _set(chave: str, valor: str, value_type: str = "string") -> None:
    row = SystemConfig.query.filter_by(key=chave).first()
    if row is None:
        row = SystemConfig(key=chave, value_type=value_type)
        db.session.add(row)
    row.value = str(valor)
    row.value_type = value_type


@admin_format_settings_bp.route("/", methods=["GET"])
@login_required
@permission_required("system_config.format_settings")
def manage():
    moeda_simbolo = SystemConfig.get(CHAVE_MOEDA_SIMBOLO, PADRAO_MOEDA_SIMBOLO)
    moeda_casas_decimais = SystemConfig.get(CHAVE_MOEDA_CASAS_DECIMAIS, PADRAO_MOEDA_CASAS_DECIMAIS)
    data_formato = SystemConfig.get(CHAVE_DATA_FORMATO, PADRAO_DATA_FORMATO)

    return render_template(
        "core/admin/format_settings.html",
        moeda_simbolo=moeda_simbolo,
        moeda_casas_decimais=moeda_casas_decimais,
        data_formato=data_formato,
        opcoes_data_formato=_OPCOES_DATA_FORMATO,
        exemplo_moeda=formatar_moeda(1234.5),
        exemplo_data=formatar_data("2026-08-31"),
    )


@admin_format_settings_bp.route("/", methods=["POST"])
@login_required
@permission_required("system_config.format_settings")
def save():
    moeda_simbolo = (request.form.get("moeda_simbolo") or "").strip() or PADRAO_MOEDA_SIMBOLO
    data_formato = request.form.get("data_formato") or PADRAO_DATA_FORMATO
    try:
        moeda_casas_decimais = int(request.form.get("moeda_casas_decimais", PADRAO_MOEDA_CASAS_DECIMAIS))
        if moeda_casas_decimais < 0 or moeda_casas_decimais > 6:
            raise ValueError
    except ValueError:
        flash("Casas decimais deve ser um número entre 0 e 6.", "error")
        return redirect(url_for("admin_format_settings.manage"))

    _set(CHAVE_MOEDA_SIMBOLO, moeda_simbolo)
    _set(CHAVE_MOEDA_CASAS_DECIMAIS, moeda_casas_decimais, value_type="int")
    _set(CHAVE_DATA_FORMATO, data_formato)
    db.session.commit()

    flash("Formatação atualizada — vale para o sistema inteiro.", "success")
    return redirect(url_for("admin_format_settings.manage"))
