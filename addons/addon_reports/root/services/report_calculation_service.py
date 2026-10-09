"""Condições tipadas e agregações limitadas, sem execução de expressões."""
from decimal import Decimal, InvalidOperation, localcontext
import math

AGGREGATES = ('sum', 'avg', 'min', 'max', 'count')


def scalar(value):
    return value is None or type(value) in (str, bool, int) or (type(value) is float and math.isfinite(value))


def validate_condition(spec):
    return (type(spec) is dict and set(spec) == {'binding', 'operator', 'value'}
            and type(spec['operator']) is str and spec['operator'] in ('eq', 'ne')
            and scalar(spec['value']) and (type(spec['value']) is not str or len(spec['value']) <= 1000))


def condition_matches(value, spec):
    if not scalar(value):
        raise ValueError('condition')
    expected = spec['value']
    # Números JSON se comparam entre si; booleano não se confunde com 0/1.
    numeric = type(value) in (int, float) and type(expected) in (int, float)
    equal = (numeric or type(value) is type(expected)) and value == expected
    return equal if spec['operator'] == 'eq' else not equal


def aggregate(values, kind):
    if kind == 'count':
        return len(values)
    numbers = []
    for value in values:
        if value is None:
            continue
        if type(value) not in (str, int, float) or len(str(value)) > 100:
            raise ValueError('aggregate')
        try:
            number = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError('aggregate') from exc
        if not number.is_finite() or (number and not -18 <= number.adjusted() <= 18):
            raise ValueError('aggregate')
        numbers.append(number)
    if not numbers:
        return '0' if kind == 'sum' else None
    with localcontext() as context:
        context.prec = 40
        result = sum(numbers, Decimal(0)) if kind in ('sum', 'avg') else min(numbers) if kind == 'min' else max(numbers)
        if kind == 'avg':
            result /= len(numbers)
    # Formatação existente recebe string decimal, sem perda por float.
    return str(result)
