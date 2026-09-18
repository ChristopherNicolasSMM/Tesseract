"""
addons/addon_brewstation/features/feature_ingredientes/services/preco_padrao_seed.py

Seed idempotente das 3 linhas de PrecoPadraoInsumo (malte, lupulo,
levedura) — nunca sobrescreve um valor já existente, só cria o que
falta. Chamado no boot (core/app_factory.py), mesmo padrão de
addon_estoque/root/services/estoque_seed.py.

Guarda de OperationalError/ProgrammingError: mesmo motivo do
estoque_seed.py — em boot de FlaskGroup, create_app() roda antes de
`flask db upgrade`, então a tabela pode não existir fisicamente ainda
na primeira execução depois de adicionar este model.
"""
import logging

from sqlalchemy.exc import OperationalError, ProgrammingError

from core.db import db
from addons.addon_brewstation.features.feature_ingredientes.model.preco_padrao_insumo import (
    PrecoPadraoInsumo,
    TIPOS_INSUMO,
)

logger = logging.getLogger(__name__)

# Valores iniciais só pra não nascer em zero — editáveis a qualquer
# momento via popup na tela de workspace (feature_envase cai neles só
# quando não existe preço real pago pro Material daquele tipo).
_VALOR_INICIAL = {
    "malte": 25.0,
    "lupulo": 120.0,
    "levedura": 15.0,
}


def ensure_default_precos_padrao_insumo() -> None:
    try:
        existentes = {p.tipo_insumo for p in PrecoPadraoInsumo.query.all()}
    except (OperationalError, ProgrammingError):
        logger.debug("Tabela preco_padrao_insumo ainda não existe (migration pendente) — seed adiado.")
        db.session.rollback()
        return

    criou_algum = False
    for tipo in TIPOS_INSUMO:
        if tipo in existentes:
            continue
        db.session.add(PrecoPadraoInsumo(
            tipo_insumo=tipo,
            valor_padrao=_VALOR_INICIAL.get(tipo, 0.0),
            unidade="kg" if tipo != "levedura" else "un",
        ))
        criou_algum = True

    if criou_algum:
        db.session.commit()
        logger.info("Preços padrão de insumo seedados (malte/lupulo/levedura).")
