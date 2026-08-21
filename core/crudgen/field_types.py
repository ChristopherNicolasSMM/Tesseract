"""
core/crudgen/field_types.py

Skill 20 (docs/skills/20-proposta-crudgen-tipo-sqlalchemy-html.md):
mapeia o tipo REAL de uma coluna SQLAlchemy pra um `html_type` de
formulário (date/datetime-local/time/number/checkbox/textarea/text),
usado pelo controller gerado (`controller.py.j2`) pra enriquecer
`_FIELD_HTML_VALIDATIONS` — sem criar annotation nova (`@calendar`
avaliada e descartada na skill 20, seção H: redundante com `db.Date`).

Isolado num módulo próprio (em vez de `annotations/__init__.py` ou
`core/crudgen/generator.py`) por decisão explícita da skill 20, seção
L — nenhum dos dois precisa mudar; isso é o único arquivo novo do
lado Python desta fase.
"""
from __future__ import annotations

import datetime

import sqlalchemy as sa


def html_type_for_column(column) -> dict:
    """
    Retorna {"html_type": str} (+ "step" quando fizer sentido) pro tipo
    real da coluna. Tipo customizado/derivado ou não reconhecido NUNCA
    levanta exceção — cai em {"html_type": "text"}, mesmo
    comportamento de hoje (skill 20, seção N: mesmo padrão de
    try/except que `_coerce_value` já usa, service.py.j2).
    """
    try:
        # Só pra confirmar que o tipo é "normal" o bastante pra ter um
        # python_type resolvível — não usamos o valor em si abaixo,
        # os `isinstance` contra sa.* são mais precisos que python_type
        # pra distinguir Text de String (os dois retornam `str`) e
        # Date de DateTime (isinstance não tem essa ambiguidade).
        column.type.python_type
    except (NotImplementedError, AttributeError):
        return {"html_type": "text"}

    col_type = column.type

    if isinstance(col_type, sa.Boolean):
        return {"html_type": "checkbox"}
    if isinstance(col_type, sa.DateTime):
        return {"html_type": "datetime-local"}
    if isinstance(col_type, sa.Date):
        return {"html_type": "date"}
    if isinstance(col_type, sa.Time):
        return {"html_type": "time"}
    if isinstance(col_type, sa.Text):
        # sa.Text é subclasse de sa.String — precisa vir antes do
        # fallback de texto simples, mas não tem equivalente "number".
        return {"html_type": "textarea"}
    if isinstance(col_type, sa.Integer):
        return {"html_type": "number", "step": "1"}
    if isinstance(col_type, (sa.Float, sa.Numeric)):
        return {"html_type": "number", "step": "any"}

    return {"html_type": "text"}


def html_types_for_model(model_class, editable_fields: list[str]) -> dict:
    """
    Monta {field: {"html_type": ..., "step": ...}} pra todo campo
    editável do model — usado por `controller.py.j2` (skill 20).
    """
    return {
        c.name: html_type_for_column(c)
        for c in model_class.__table__.columns
        if c.name in editable_fields
    }
