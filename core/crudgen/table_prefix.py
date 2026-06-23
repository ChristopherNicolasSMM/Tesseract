"""
core/crudgen/table_prefix.py

Aplica o prefixo tri-nível completo (skill 02) ao __table__ de um
model, em runtime — o desenvolvedor escreve __tablename__ curto
("yeast_strain"), o CrudGen aplica "tesseract_brewstation_yeastbank_"
na hora da geração.

Decisão registrada (BACKLOG.md): a skill 02 fala em aplicar o prefixo
"no momento do registro" no ModuleManager — aqui aplicamos no momento
da GERAÇÃO (CrudGen), que produz o mesmo efeito prático (o nome físico
da tabela já nasce certo) com bem menos máquina. Revisitar se a Fase 5
(primeiro Addon real, com Features e FK entre tabelas do mesmo Addon)
expuser um caso em que isso não seja suficiente.
"""
import logging

logger = logging.getLogger(__name__)


def apply_table_prefix(model_class, full_prefix: str) -> str:
    """
    full_prefix: já resolvido por manifest_utils.resolve_table_prefix(),
    sem o "tesseract_" inicial (ex.: "brewstation_yeastbank").

    Idempotente — chamar duas vezes não duplica o prefixo.
    Retorna o nome final da tabela.
    """
    table = model_class.__table__
    old_name = table.name
    expected_prefix = f"tesseract_{full_prefix}_"

    if old_name.startswith(expected_prefix):
        logger.debug("Tabela já prefixada: %s", old_name)
        return old_name

    new_name = f"{expected_prefix}{old_name}"
    metadata = table.metadata

    metadata._remove_table(old_name, table.schema)
    table.name = new_name
    metadata._add_table(new_name, table.schema, table)
    model_class.__tablename__ = new_name

    logger.info("Prefixo de tabela aplicado: %s -> %s", old_name, new_name)
    return new_name
