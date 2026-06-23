"""
tests/test_phase3_versioning.py

Cobre: seed de system_config, snapshot_if_needed (criação, on_diff
sem mudança, generation_run_id agrupando, captura de edição manual
perdida via PRE_OVERWRITE), e cleanup_old_snapshots.
"""
import tempfile
from pathlib import Path

import pytest

from core.app_factory import create_app
from core.db import db
from core.versioning import (
    start_generation_run,
    snapshot_if_needed,
    cleanup_old_snapshots,
)
from model.core.code_snapshot import CodeSnapshot, SnapshotOrigin
from model.core.system_config import SystemConfig


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


def test_seed_cria_chaves_padrao_de_versioning(app):
    with app.app_context():
        assert SystemConfig.get("versioning.enabled") is True
        assert SystemConfig.get("versioning.trigger") == "on_diff"
        assert SystemConfig.get("versioning.retention_days") == 0


def test_seed_eh_idempotente(app):
    from core.seed_config import ensure_default_system_config

    with app.app_context():
        ensure_default_system_config()
        ensure_default_system_config()
        count = SystemConfig.query.filter_by(key="versioning.enabled").count()
        assert count == 1


def test_snapshot_eh_criado_para_arquivo_novo(app):
    with app.app_context():
        start_generation_run("Recipe", triggered_by="cli:generate")
        snap = snapshot_if_needed("addons/addon_test/model/recipe.py", "conteudo v1")
        assert snap is not None
        assert snap.is_current is True
        assert snap.content == "conteudo v1"


def test_on_diff_nao_versiona_conteudo_identico(app):
    with app.app_context():
        snapshot_if_needed("x.py", "mesmo conteudo")
        segundo = snapshot_if_needed("x.py", "mesmo conteudo")
        assert segundo is None  # nada mudou — on_diff não versiona de novo


def test_generation_run_agrupa_varios_arquivos(app):
    with app.app_context():
        run_id = start_generation_run("Recipe", triggered_by="cli:generate")
        s1 = snapshot_if_needed("a.py", "conteudo a")
        s2 = snapshot_if_needed("b.py", "conteudo b")
        assert s1.generation_run_id == run_id
        assert s2.generation_run_id == run_id


def test_segunda_versao_marca_anterior_como_nao_corrente(app):
    with app.app_context():
        primeiro = snapshot_if_needed("y.py", "v1")
        segundo = snapshot_if_needed("y.py", "v2")

        db.session.refresh(primeiro)
        assert primeiro.is_current is False
        assert segundo.is_current is True
        assert segundo.parent_snapshot_id == primeiro.id


def test_captura_edicao_manual_perdida_antes_de_sobrescrever(app):
    """
    Simula: gerar um arquivo (snapshot v1) -> alguém edita o arquivo
    direto no disco, fora do gerador -> gerador roda de novo com
    --overwrite. A edição manual precisa aparecer no histórico
    (origin=PRE_OVERWRITE) antes de ser sobrescrita.
    """
    with app.app_context():
        with tempfile.TemporaryDirectory() as tmp:
            file_path = str(Path(tmp) / "arquivo_gerado.py")

            snapshot_if_needed(file_path, "versao gerada original")

            # edição manual direta no disco, sem passar por snapshot_if_needed
            Path(file_path).write_text("versao editada manualmente", encoding="utf-8")

            # gerador roda de novo, tentando sobrescrever com uma 3ª versão
            snapshot_if_needed(file_path, "versao gerada nova")

            historico = (
                CodeSnapshot.query
                .filter_by(file_path=file_path)
                .order_by(CodeSnapshot.created_at.asc())
                .all()
            )

            origins = [s.origin for s in historico]
            assert SnapshotOrigin.GENERATED in origins
            assert SnapshotOrigin.PRE_OVERWRITE in origins
            # a edição manual não se perdeu — está no histórico
            conteudos = [s.content for s in historico]
            assert "versao editada manualmente" in conteudos


def test_cleanup_nao_remove_nada_com_retention_zero(app):
    with app.app_context():
        snapshot_if_needed("z.py", "v1")
        snapshot_if_needed("z.py", "v2")
        removidos = cleanup_old_snapshots()
        assert removidos == 0  # retention_days=0 e retention_max=0 (padrão)


def test_cleanup_respeita_retention_max_per_file(app):
    with app.app_context():
        SystemConfig.query.filter_by(key="versioning.retention_max_per_file").delete()
        db.session.add(
            SystemConfig(key="versioning.retention_max_per_file", value="2", value_type="int")
        )
        db.session.commit()

        snapshot_if_needed("w.py", "v1")
        snapshot_if_needed("w.py", "v2")
        snapshot_if_needed("w.py", "v3")

        removidos = cleanup_old_snapshots()
        assert removidos == 1  # mantém 2 (1 corrente + 1 antiga), remove a mais antiga

        restantes = CodeSnapshot.query.filter_by(file_path="w.py").count()
        assert restantes == 2
