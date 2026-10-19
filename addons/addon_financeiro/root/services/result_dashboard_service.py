"""Comparativos e margens derivados exclusivamente da DRE, sem lucro presumido."""
import calendar
from datetime import date
from decimal import Decimal,ROUND_HALF_UP
from . import accrual_service as a,treasury_service as t,cash_flow_service as f


def shift(month,offset):
    value=month.year*12+month.month-1+offset
    year,zero=divmod(value,12)
    if not 1<=year<=9999:raise ValueError('Período comparativo fora do calendário suportado.')
    return date(year,zero+1,1)


def ratio(numerator,denominator):
    if denominator<=0:return None
    return t.canonical((numerator*100/denominator).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP))


@f.exact
def dashboard(options):
    options=t.fields(options,{'organization_code','date_from','date_to'})
    current=a.statement(options)
    count=len(current['months'])
    if count>12:raise ValueError('Dashboard admite até 12 competências por comparação.')
    start=a.day(current['date_from']);previous_start=shift(start,-count);previous_end=start.fromordinal(start.toordinal()-1)
    previous=a.statement({**options,'date_from':previous_start.isoformat(),'date_to':previous_end.isoformat()})
    rows={row['code']:row for row in current['rows']};old={row['code']:row for row in previous['rows']}
    indicators=[]
    for code,label in [('NET_REVENUE','Receita líquida'),('GROSS_RESULT','Resultado bruto'),('OPERATING_RESULT','Resultado operacional'),('NET_RESULT','Resultado líquido gerencial')]:
        value=Decimal(rows[code]['total']);prior=Decimal(old[code]['total']);delta=value-prior
        indicators.append({'code':code,'label':label,'amount':t.canonical(value),'previous':t.canonical(prior),'delta':t.canonical(delta),
            'change_percent':ratio(delta,abs(prior)),'margin_percent':ratio(value,Decimal(rows['NET_REVENUE']['total'])) if code!='NET_REVENUE' else None})
    monthly=[{'period':month,'net_revenue':rows['NET_REVENUE']['values'][month],'net_result':rows['NET_RESULT']['values'][month],
        'gross_result':rows['GROSS_RESULT']['values'][month],'operating_result':rows['OPERATING_RESULT']['values'][month]} for month in current['months']]
    categories={};centers={}
    for detail in current['details']:
        if detail['group_code'] not in ('COST','OPERATING_EXPENSE','FINANCIAL_EXPENSE','INCOME_TAX'):continue
        amount=-Decimal(detail['result_amount'])
        for target,key in ((categories,detail['category_name']),(centers,detail['cost_center_name'])):target[key]=target.get(key,Decimal(0))+amount
    formation=[{'label':rows[code]['label'],'amount':rows[code]['total'],'code':code} for code in ('REVENUE','DEDUCTIONS','COST','OPERATING_EXPENSE','FINANCIAL_INCOME','FINANCIAL_EXPENSE','INCOME_TAX','NET_RESULT')]
    return {'contract':'financeiro.results_dashboard.v1','organization_code':current['organization_code'],'organization_name':current['organization_name'],
        'currency_code':current['currency_code'],'date_from':current['date_from'],'date_to':current['date_to'],
        'previous_from':previous_start.isoformat(),'previous_to':previous_end.isoformat(),'status':current['status'],'status_label':current['status_label'],
        'pending_count':current['pending_count'],'basis':current['basis'],'closures':current['closures'],'indicators':indicators,'monthly':monthly,'formation':formation,
        'categories':[{'name':key,'amount':t.canonical(value)} for key,value in sorted(categories.items())],
        'centers':[{'name':key,'amount':t.canonical(value)} for key,value in sorted(centers.items())],
        'items':[{'label':i['label'],'amount':i['amount'],'previous':i['previous'],'delta':i['delta'],'change_percent':i['change_percent'] if i['change_percent'] is not None else 'Sem base comparável','margin_percent':i['margin_percent'] if i['margin_percent'] is not None else 'Sem base positiva'} for i in indicators]}
