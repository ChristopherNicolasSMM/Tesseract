"""
core/admin_list_helpers.py

Telas administrativas (Usuários, Roles, Transações, Regras de Campo,
OData, Designer) não passam pelo CrudGen — os models de Core (`User`,
`Role`, etc.) são escritos à mão de propósito (skill 02). Isso fez o
smart-list completo (export/filtro/colunas) só chegar nas 24 entidades
geradas, nunca nessas 12 telas — gap real, encontrado validando o
projeto com o Christopher.

Em vez de copiar a lógica de exportação/paginação 12 vezes à mão (com
12 chances de cada cópia divergir um pouco), esses helpers extraem só
a parte que de fato repete. Filtro de busca continua específico de
cada tela (cada uma teria campos de texto diferentes pra buscar) —
isso fica no controller de cada uma, só chamando `paginate()`.

Decisão registrada: sem "colunas configuráveis por usuário" aqui — as
telas administrativas têm um número pequeno e fixo de colunas
relevantes (diferente de uma entidade de domínio qualquer, que pode
ter dezenas de campos). Adicionar a configuração de colunas pra um
conjunto fixo de ~5 colunas não traria valor real.
"""
from __future__ import annotations

import csv
import io

from flask import Response


def paginate(query, page: int, per_page: int = 20):
    """
    Pagina uma query SQLAlchemy qualquer. Retorna (items, total, pages).
    Mesma lógica usada pelo CrudGen (`controller.py.j2`), só extraída
    pra ser reaproveitada pelas telas administrativas.
    """
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    pages = max(1, (total + per_page - 1) // per_page)
    return items, total, pages


def export_csv_response(headers: list[str], rows: list[list], filename: str) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
    )


def export_xlsx_response(headers: list[str], rows: list[list], filename: str, sheet_title: str = "Dados") -> Response:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]  # limite do Excel pro nome da aba
    ws.append(headers)
    for row in rows:
        ws.append([str(v) if v is not None else "" for v in row])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return Response(
        buffer.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"},
    )
