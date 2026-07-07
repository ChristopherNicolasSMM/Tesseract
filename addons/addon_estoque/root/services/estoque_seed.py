"""
addons/addon_estoque/root/services/estoque_seed.py

Seed idempotente dos registros de lookup usados como resolução
automática pelo autocreate de feature_brew_father (decisão desta
sessão, ver BACKLOG.md): Origem "A definir" e TipoProduto "Insumo".
Chamado no boot (core/app_factory.py, mesmo padrão de
core/seed_config.ensure_default_system_config) - nunca sobrescreve um
registro já existente, só cria o que falta.

Por que aqui e não em core/: são dados de negócio específicos de
addon_estoque (skill 00 - core nunca contém regra de domínio), mesmo
padrão já usado para o cliente MQTT de addon_device_manager, que
também é chamado a partir de app_factory.py.
"""
import logging

from core.db import db
from addons.addon_estoque.root.model.origem import Origem, SEED_NOME_A_DEFINIR
from addons.addon_estoque.root.model.tipo_produto import TipoProduto, SEED_NOME_INSUMO

logger = logging.getLogger(__name__)


def ensure_default_estoque_lookups() -> None:
    criado_algo = False

    if not Origem.query.filter_by(nome=SEED_NOME_A_DEFINIR).first():
        db.session.add(Origem(nome=SEED_NOME_A_DEFINIR))
        criado_algo = True

    if not TipoProduto.query.filter_by(nome=SEED_NOME_INSUMO).first():
        db.session.add(TipoProduto(nome=SEED_NOME_INSUMO))
        criado_algo = True

    if criado_algo:
        db.session.commit()
        logger.info("addon_estoque — lookups padrão criados (Origem/TipoProduto).")
    else:
        logger.debug("addon_estoque — lookups padrão já existem.")


def get_or_create_origem_a_definir() -> Origem:
    """Usado pelo autocreate de feature_brew_father - garante o
    registro mesmo se o boot ainda não rodou (ex.: em testes que
    criam o app mas chamam isso antes do fluxo normal)."""
    obj = Origem.query.filter_by(nome=SEED_NOME_A_DEFINIR).first()
    if not obj:
        obj = Origem(nome=SEED_NOME_A_DEFINIR)
        db.session.add(obj)
        db.session.flush()
    return obj


def get_or_create_tipo_produto_insumo() -> TipoProduto:
    """Ver get_or_create_origem_a_definir - mesmo raciocínio."""
    obj = TipoProduto.query.filter_by(nome=SEED_NOME_INSUMO).first()
    if not obj:
        obj = TipoProduto(nome=SEED_NOME_INSUMO)
        db.session.add(obj)
        db.session.flush()
    return obj
