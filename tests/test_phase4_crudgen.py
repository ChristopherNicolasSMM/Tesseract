"""
tests/test_phase4_crudgen.py

Cobre: resolução de prefixo de tabela a partir de addon.json,
aplicação do prefixo no model, geração dos arquivos esperados,
preservação de hooks/arquivos existentes sem --overwrite, e
sincronização de permissões Camada 1 (automática) + Camada 2
(@permission).

Nota importante: a metadata do SQLAlchemy (db.Model) é um singleton
por processo — por isso o model de smoke-test é definido uma única
vez, em nível de módulo, e reaproveitado por todos os testes deste
arquivo (redefinir a classe a cada teste duplicaria a Table e
quebraria com "Table already defined").
"""
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from core.app_factory import create_app
from core.db import db
from annotations import label, plural, permission
from core.crudgen.generator import generate
from model.core.permission import Permission


# ── Projeto temporário com um addon_smoketest válido ────────────────────────

_tmp_dir = tempfile.mkdtemp(prefix="tesseract_crudgen_test_")
_PROJECT_ROOT = Path(_tmp_dir)

_addon_dir = _PROJECT_ROOT / "addons" / "addon_smoketest"
_addon_dir.mkdir(parents=True, exist_ok=True)
(_addon_dir / "addon.json").write_text(
    json.dumps({"name": "smoketest", "table_prefix": "smoketest"}), encoding="utf-8"
)


def _cleanup_tmp_dir():
    shutil.rmtree(_tmp_dir, ignore_errors=True)


# ── Model de smoke-test (definido UMA VEZ, nível de módulo) ────────────────

@label("Item de Teste")
@plural("smoketest_items")
@permission("approve", role_required="tester", description="Aprovar item de teste")
class SmoketestItem(db.Model):
    __tablename__ = "item"  # nome curto — CrudGen aplica o prefixo (skill 02)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)

    def to_dict(self):
        return {"id": self.id, "name": self.name}


@pytest.fixture(scope="module")
def app():
    app = create_app(env="testing")
    yield app
    _cleanup_tmp_dir()


@pytest.fixture(scope="module")
def generated(app):
    """Roda generate() uma única vez para todo o módulo de teste."""
    with app.app_context():
        result = generate(
            SmoketestItem,
            project_root=_PROJECT_ROOT,
            addon="smoketest",
            overwrite=False,
        )
        yield result


def test_tabela_recebe_prefixo_tri_nivel_correto(generated):
    assert SmoketestItem.__tablename__ == "tesseract_smoketest_item"
    assert generated["table_name"] == "tesseract_smoketest_item"


def test_aplicar_prefixo_duas_vezes_eh_idempotente(app):
    from core.crudgen.table_prefix import apply_table_prefix

    with app.app_context():
        nome1 = apply_table_prefix(SmoketestItem, "smoketest")
        nome2 = apply_table_prefix(SmoketestItem, "smoketest")
        assert nome1 == nome2 == "tesseract_smoketest_item"


def test_gera_os_7_arquivos_esperados(generated):
    written = generated["written"]
    assert len(written) == 9  # service + service_hooks + controller + controller_hooks
    #                          # + routes + routes_hooks + manage.html + detail.html + form_modal.html

    nomes = [Path(p).name for p in written]
    assert "smoketest_item_service.py" in nomes
    assert "smoketest_item_service_hooks.py" in nomes
    assert "smoketest_items.py" in nomes  # controller
    assert "smoketest_items_hooks.py" in nomes
    assert "smoketest_items_routes.py" in nomes
    assert "smoketest_items_routes_hooks.py" in nomes
    assert "manage.html" in nomes
    assert "detail.html" in nomes
    assert "form_modal.html" in nomes


def test_servico_gerado_usa_soft_delete_is_deleted(generated):
    service_file = [p for p in generated["written"] if p.endswith("_service.py")][0]
    content = Path(service_file).read_text(encoding="utf-8")
    assert "is_deleted" in content
    assert "deleted_at" in content
    assert "def trash(" in content
    assert "def restore(" in content
    assert "def delete_permanent(" in content


def test_segunda_geracao_sem_overwrite_preserva_hooks_e_arquivos(app, generated):
    with app.app_context():
        resultado2 = generate(
            SmoketestItem,
            project_root=_PROJECT_ROOT,
            addon="smoketest",
            overwrite=False,
        )
    assert len(resultado2["written"]) == 0
    assert len(resultado2["skipped_hooks"]) == 3       # service_hooks + controller_hooks + routes_hooks
    assert len(resultado2["skipped_existing"]) == 6     # service/controller/routes/3 templates HTML


def test_segunda_geracao_com_overwrite_regenera_mas_preserva_hooks(app, generated):
    with app.app_context():
        resultado = generate(
            SmoketestItem,
            project_root=_PROJECT_ROOT,
            addon="smoketest",
            overwrite=True,
        )
    assert len(resultado["written"]) == 6   # tudo, exceto os 3 hooks (sempre preservados)
    assert len(resultado["skipped_hooks"]) == 3


def test_permissoes_camada_1_e_camada_2_sincronizadas(app, generated):
    with app.app_context():
        nomes = {p.name for p in Permission.query.all()}
        # Camada 1 — automática, 7 ações padrão
        for action in ("list", "detail", "create", "update", "trash", "restore", "delete_permanent"):
            assert f"smoketest_items.{action}" in nomes
        # Camada 2 — via @permission no model
        assert "smoketest_items.approve" in nomes


def test_permissao_camada_2_cria_role_automaticamente(app, generated):
    from model.core.role import Role

    with app.app_context():
        role = Role.query.filter_by(name="tester").first()
        assert role is not None
        perm_names = {p.name for p in role.permissions}
        assert "smoketest_items.approve" in perm_names
