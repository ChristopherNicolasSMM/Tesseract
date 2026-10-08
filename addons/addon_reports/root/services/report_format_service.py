"""Apresentação pt-BR determinística; sem conversão monetária ou eval."""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

KINDS = ('raw', 'number', 'currency', 'percent', 'date', 'datetime')


def validate_format(spec):
    if type(spec) is not dict or set(spec)-{'kind','decimals','currency','null_text'}:
        return False
    kind=spec.get('kind','raw')
    if type(kind) is not str or kind not in KINDS:
        return False
    if 'decimals' in spec and (kind not in ('number','currency','percent') or type(spec['decimals']) is not int or not 0<=spec['decimals']<=6):
        return False
    if 'currency' in spec and (kind!='currency' or spec['currency'] not in ('BRL','USD','EUR')):
        return False
    return 'null_text' not in spec or (type(spec['null_text']) is str and len(spec['null_text'])<=120)


def format_value(value, spec):
    kind=spec.get('kind','raw')
    if value is None:
        return spec.get('null_text','')
    if kind=='raw':
        return str(value)
    if kind in ('date','datetime'):
        if type(value) is not str:
            raise ValueError('date')
        if kind=='date':
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError('date')
            return date.fromisoformat(value).strftime('%d/%m/%Y')
        if not re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', value):
            raise ValueError('datetime')
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        return parsed.strftime('%d/%m/%Y %H:%M:%S') + (' '+parsed.strftime('%z') if parsed.tzinfo else '')
    if type(value) not in (str,int,float) or len(str(value))>100:
        raise ValueError('number')
    try:
        number=Decimal(str(value))
        if not number.is_finite() or (number and not -18<=number.adjusted()<=18):
            raise ValueError('number')
        with localcontext() as context:
            context.prec=40
            if kind=='percent':number*=100
            number=number.quantize(Decimal(1).scaleb(-spec.get('decimals',2)), rounding=ROUND_HALF_UP)
        output=format(number, ',f').replace(',','_').replace('.',',').replace('_','.')
    except InvalidOperation as exc:
        raise ValueError('number') from exc
    if kind=='currency':
        output={'BRL':'R$', 'USD':'US$', 'EUR':'€'}[spec.get('currency','BRL')]+' '+output
    elif kind=='percent':output+=' %'
    return output
