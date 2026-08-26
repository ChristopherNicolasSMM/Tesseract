"""
addons/addon_estoque/root/services/estoque_seed.py

Seed idempotente dos registros de lookup usados como resolução
automática pelo autocreate de feature_brew_father (decisão de sessão
anterior, ver BACKLOG.md): Origem "A definir" e TipoProduto "Insumo".
Chamado no boot (core/app_factory.py, mesmo padrão de
core/seed_config.ensure_default_system_config) - nunca sobrescreve um
registro já existente, só cria o que falta.

CORREÇÃO DE BUG REAL (skill 23, achado ao rodar a suíte de testes
antes de iniciar a Fase 1): o insert de TipoProduto "Insumo" não
preenchia `codigo` (coluna NOT NULL, unique) - `IntegrityError` em
QUALQUER boot que passasse por este seed (inclusive toda a suíte
`tests/test_addon_estoque.py`, 19 testes quebrados só por isso, nada
relacionado à Fase 1 em si). Corrigido aqui, e os 4 seeds novos da
Fase 1 (Embalagem/Produto Acabado/Peça/Uso e Consumo) já nascem com
`codigo` preenchido para não repetir o mesmo erro.

Por que aqui e não em core/: são dados de negócio específicos de
addon_estoque (skill 00 - core nunca contém regra de domínio), mesmo
padrão já usado para o cliente MQTT de addon_device_manager, que
também é chamado a partir de app_factory.py.

Guarda de OperationalError/ProgrammingError (achado real, sessão
2026-08-25): `run.py` usa FlaskGroup, então `create_app()` — com todo
seed de boot, este incluído — roda ANTES de qualquer subcomando
`flask db ...` ser processado, inclusive `db migrate`/`db upgrade`.
Quando um campo novo é adicionado a `Origem`/`TipoProduto` e a
migration ainda não foi gerada/aplicada, a coluna não existe fisicamente
no banco nesse instante — sem esta guarda, o boot inteiro quebra antes
até de `flask db migrate` conseguir comparar o schema (erro circular:
não dá pra gerar a migration que criaria a coluna porque o boot morre
antes). Mesmo padrão já usado em core/odata_local_seed.py e
core/designer_menu_override.py: se a coluna não existe ainda, adia o
seed (debug, não erro) — o próximo boot, já com a migration aplicada,
seeda normalmente. Instalação nova (banco criado do zero via
db.create_all()) nunca cai aqui, porque a coluna já nasce junto.
"""
import logging

from sqlalchemy.exc import OperationalError, ProgrammingError

from core.db import db
from addons.addon_estoque.root.model.origem import Origem, SEED_NOME_A_DEFINIR
from addons.addon_estoque.root.model.tipo_produto import (
    TipoProduto,
    SEED_NOME_INSUMO,
    SEED_NOME_EMBALAGEM,
    SEED_NOME_PRODUTO_ACABADO,
    SEED_NOME_PECA,
    SEED_NOME_USO_E_CONSUMO,
)

logger = logging.getLogger(__name__)

# codigo é NOT NULL/unique em TipoProduto - mapa fixo pra manter os
# seeds idempotentes e nunca repetir o bug de insert sem codigo.
_TIPOS_PRODUTO_SEED = {
    SEED_NOME_INSUMO: "INSUMO",
    SEED_NOME_EMBALAGEM: "EMBALAGEM",
    SEED_NOME_PRODUTO_ACABADO: "PRODUTO_ACABADO",
    SEED_NOME_PECA: "PECA",
    SEED_NOME_USO_E_CONSUMO: "USO_E_CONSUMO",
}


def ensure_default_estoque_lookups() -> None:
    try:
        criado_algo = False

        if not Origem.query.filter_by(nome=SEED_NOME_A_DEFINIR).first():
            db.session.add(Origem(nome=SEED_NOME_A_DEFINIR))
            criado_algo = True

        for descricao, codigo in _TIPOS_PRODUTO_SEED.items():
            if not TipoProduto.query.filter_by(descricao=descricao).first():
                db.session.add(TipoProduto(descricao=descricao, codigo=codigo))
                criado_algo = True

        if criado_algo:
            db.session.commit()
            logger.info("addon_estoque — lookups padrão criados (Origem/TipoProduto).")
        else:
            logger.debug("addon_estoque — lookups padrão já existem.")
    except (OperationalError, ProgrammingError):
        db.session.rollback()
        logger.debug(
            "addon_estoque — schema de Origem/TipoProduto ainda não está "
            "atualizado (migration pendente) — seed dos lookups padrão adiado."
        )


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
    obj = TipoProduto.query.filter_by(descricao=SEED_NOME_INSUMO).first()
    if not obj:
        obj = TipoProduto(descricao=SEED_NOME_INSUMO, codigo=_TIPOS_PRODUTO_SEED[SEED_NOME_INSUMO])
        db.session.add(obj)
        db.session.flush()
    return obj
