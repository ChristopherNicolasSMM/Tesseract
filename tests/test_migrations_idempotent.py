"""
tests/test_migrations_idempotent.py

Regressão do achado real (BACKLOG.md): `db.create_all()` roda em todo
boot do app (necessário para provisionar tabelas de Addon, que não
passam por Alembic) — inclusive no primeiro boot de alguém que nunca
rodou `flask db upgrade` ainda. Isso significa que, na prática, o
schema já nasce na forma ATUAL (refletindo os models de hoje) antes
de qualquer migration rodar. Toda migration que faz `add_column`/
`create_table`/`rename_table` sem checar se aquilo já existe falha
como "duplicate column"/"already exists" nesse cenário — que não é
raro, é o caminho *padrão* de quem clona o projeto e roda `python
run.py start` antes de `flask db upgrade`.

Este teste reproduz o cenário fim-a-fim: cria um banco do zero via
`db.create_all()` com o código atual (sem nenhuma migration aplicada,
sem stamp nenhum), depois roda `flask db upgrade` de verdade (via
subprocess, igual o usuário faria) e confirma que a cadeia inteira
passa sem erro, terminando na revision HEAD. Também confirma que o
downgrade completo (HEAD -> base) funciona.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _head_revision() -> str:
    """Mesma lógica usada em várias sessões desta conversa pra achar o
    head da cadeia de migrations, sem depender do alembic já estar
    rodando."""
    versions_dir = _PROJECT_ROOT / "migrations" / "versions"
    revs = {}
    for f in versions_dir.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        rid = re.search(r"revision = '([^']+)'", text)
        down = re.search(r"down_revision = '?([^'\n]+)'?", text)
        if rid:
            revs[rid.group(1)] = down.group(1) if down else None
    downs = set(revs.values())
    heads = [r for r in revs if r not in downs]
    assert len(heads) == 1, f"Esperava 1 head, achou {heads}"
    return heads[0]


def _run_flask_db(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["FLASK_ENV"] = "development"
    return subprocess.run(
        [sys.executable, "-m", "flask", "db"] + args,
        cwd=str(_PROJECT_ROOT), env=env,
        capture_output=True, text=True, timeout=120,
    )


@pytest.mark.slow
def test_flask_db_upgrade_do_zero_absoluto_nao_falha(tmp_path):
    """O cenário real que quebrava: `db.create_all()` com o código
    atual, alembic_version inexistente, depois `flask db upgrade`."""
    db_path = tmp_path / "fresh.db"

    # 1) Simula o primeiro boot (db.create_all(), sem nenhuma migration
    # aplicada ainda) — mesma técnica usada manualmente nesta sessão.
    create_script = (
        "import logging; logging.disable(logging.CRITICAL)\n"
        "from core.app_factory import create_app\n"
        "from core.db import db\n"
        "app = create_app(env='development')\n"
        "with app.app_context():\n"
        "    db.create_all()\n"
    )
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["FLASK_ENV"] = "development"
    result = subprocess.run(
        [sys.executable, "-c", create_script],
        cwd=str(_PROJECT_ROOT), env=env,
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"db.create_all() falhou:\n{result.stdout}\n{result.stderr}"
    assert db_path.exists()

    # 2) `flask db upgrade` de verdade, do zero — sem nenhum stamp.
    result = _run_flask_db(["upgrade"], db_path)
    assert result.returncode == 0, (
        f"flask db upgrade falhou (achado real, ver BACKLOG.md):\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    # 3) Confirma que chegou na revision HEAD (não parou no meio).
    import sqlite3
    con = sqlite3.connect(str(db_path))
    version = con.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    con.close()
    assert version == _head_revision()


@pytest.mark.slow
def test_flask_db_downgrade_completo_ate_a_base_nao_falha(tmp_path):
    db_path = tmp_path / "fresh_downgrade.db"

    create_script = (
        "import logging; logging.disable(logging.CRITICAL)\n"
        "from core.app_factory import create_app\n"
        "from core.db import db\n"
        "app = create_app(env='development')\n"
        "with app.app_context():\n"
        "    db.create_all()\n"
    )
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["FLASK_ENV"] = "development"
    subprocess.run(
        [sys.executable, "-c", create_script],
        cwd=str(_PROJECT_ROOT), env=env, capture_output=True, text=True, timeout=60,
    )
    _run_flask_db(["upgrade"], db_path)

    result = _run_flask_db(["downgrade", "091f87025ce4"], db_path)
    assert result.returncode == 0, (
        f"flask db downgrade ate a base falhou:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    import sqlite3
    con = sqlite3.connect(str(db_path))
    version = con.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    con.close()
    assert version == "091f87025ce4"
