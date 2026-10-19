"""Contrato público de custos congelados; não reconhece resultado nem altera estoque."""
import json
from decimal import Decimal
from services.core.organization_service import resolve_organization_by_code
from ..model.organization_stock import OrganizationMovement


def list_cost_sources(organization_code):
    org=resolve_organization_by_code(organization_code,require_active=False)['code']
    rows=OrganizationMovement.query.filter_by(organization_code=org).order_by(OrganizationMovement.id).limit(2001).all()
    if len(rows)>2000:raise ValueError('Integração de custos excede 2000 movimentos; requer consulta segmentada antes de ampliar o cadastro.')
    items=[]
    reversed_ids={json.loads(row.snapshot_json).get('reversal_of') for row in rows}
    for row in rows:
        snapshot=json.loads(row.snapshot_json);request=json.loads(row.request_json);key=row.idempotency_key
        capitalized=key.startswith(('production:','packaging:','finished:'))
        excluded=key.startswith(('transfer:','reverse-','reconcile:')) or bool(snapshot.get('transfer_reference') or snapshot.get('reversal_of'))
        eligible=row.kind in ('saida','ajuste') and row.value_delta<0 and not capitalized and not excluded and row.id not in reversed_ids
        if not eligible and not capitalized:continue
        date=snapshot.get('operation_date') or request.get('operation_date')
        items.append({'movement_id':row.id,'organization_code':org,'currency_code':row.currency_code,'amount':format(abs(row.value_delta),'f'),
            'operation_date':date,'material_id':row.material_id,'quantity':format(row.quantity_delta,'f'),
            'eligible':eligible and bool(date),'capitalized':capitalized,'reference':key,'policy':snapshot.get('policy'),
            'movement':row.to_dict(),'status':'CANDIDATE' if eligible and date else 'CAPITALIZED' if capitalized else 'REVIEW_REQUIRED'})
    return {'contract':'estoque.financial_costs.v1','organization_code':org,'items':items}
