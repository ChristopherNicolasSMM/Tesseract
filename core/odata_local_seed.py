"""
core/odata_local_seed.py

Seed idempotente da ODataConnection que representa o provedor OData do
próprio Tesseract (Fase 10, Patch 1) — mesmo padrão de
core/seed_config.py (nunca duplica, nunca sobrescreve o que já existe,
só cria se faltar).

O endpoint HTTP real (/api/odata-provider/...) é peça do Patch 2 — o
base_url já é fixado aqui porque faz parte da identidade da conexão
(muda o base_url de uma ODataConnection existente exigiria ela deixar
de ser encontrada por quem já a referencia via connection_id, então o
valor é decidido de uma vez, não fica em aberto para o Patch 2 mudar).
"""
import logging

from sqlalchemy.exc import OperationalError, ProgrammingError

from core.db import db
from model.core.odata_connection import ODataConnection

logger = logging.getLogger(__name__)

LOCAL_CONNECTION_NAME = "Tesseract (local)"
LOCAL_CONNECTION_BASE_URL = "/api/odata-provider"


def ensure_local_odata_connection():
    """
    Achado real (validação do Patch 1): `run.py` usa FlaskGroup, então
    `create_app()` — com todos os seeds de boot, este incluído — roda
    ANTES de qualquer subcomando `flask db ...` ser processado,
    inclusive `db upgrade`. Numa instalação já existente (tabela
    `tesseract_odata_connection` criada antes desta fase, migration
    ainda não aplicada), a coluna `is_local` não existe ainda nesse
    instante — sem esta guarda, o boot inteiro quebra antes que
    `flask db upgrade` tenha a chance de rodar. Mesmo espírito
    defensivo das migrations (`_column_exists`), só que em runtime:
    se a coluna não existe ainda, pula o seed (debug, não erro) — o
    próximo boot, já com a migration aplicada, seeda normalmente.
    Instalação nova (banco criado do zero via db.create_all()) nunca
    cai aqui, porque a coluna já nasce junto no create_all.
    """
    try:
        existing = ODataConnection.query.filter_by(is_local=True).first()
    except (OperationalError, ProgrammingError):
        db.session.rollback()
        logger.debug(
            "ODataConnection.is_local ainda não existe no banco (migration "
            "Fase 10/Patch 1 pendente) — seed da conexão local adiado."
        )
        return None

    if existing is not None:
        return existing

    conn = ODataConnection(
        name=LOCAL_CONNECTION_NAME,
        base_url=LOCAL_CONNECTION_BASE_URL,
        auth_type="none",
        is_local=True,
    )
    db.session.add(conn)
    db.session.commit()
    logger.info("ODataConnection local seedada (id=%s).", conn.id)
    return conn
