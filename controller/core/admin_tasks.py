"""
controller/core/admin_tasks.py

Tela HTML do Monitor de Tarefas. Portado do PyTeca
(controller/core/admin/task_monitor.py) — só a rota muda (skill 00:
sem subpasta admin/ para controller no Tesseract, diferente de
api/routes/core/admin/ e templates/core/admin/, que mantêm a
subpasta — ver docs/skills/05-proposta-addon-device-manager-e-mqtt.md
para o porquê dessa convenção mista já existir no projeto).
"""
from flask import Blueprint, render_template
from flask_login import login_required

from core.permissions import permission_required

admin_tasks_bp = Blueprint("admin_tasks", __name__, url_prefix="/admin/tasks")


@admin_tasks_bp.route("/")
@login_required
@permission_required("admin")
def index():
    return render_template("core/admin/task_monitor.html")
