"""Tesouraria organizacional. Histórico append-only e transações sem commits parciais."""
import calendar
import json
from datetime import date
from decimal import Decimal, localcontext, ROUND_DOWN
from functools import wraps
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from core.db import db
from services.core.organization_service import Result, resolve_organization_by_code
from ..model.monetary import Currency
from ..model.treasury import (FinancialAccount as Account, FinancialCategory as Category,
    FinancialCostCenter as Center, FinancialTitle as Title, FinancialInstallment as Installment,
    FinancialSettlement as Settlement, FinancialReversal as Reversal,
    FinancialCancellation as Cancellation, FinancialMovement as Movement)
from .exchange_service import text, day, decimal_text, preview_conversion
from .policy_version_service import resolve_selected_policy
from .monetary_service import ROUNDINGS

CATALOGS = {'accounts': Account, 'categories': Category, 'cost-centers': Center}


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def canonical(value):
    value = Decimal(value)
    raw = format(value, 'f')
    return (raw.rstrip('0').rstrip('.') if '.' in raw else raw) if value else '0'


def ident(value, *, optional=False):
    if value is None and optional: return None
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise ValueError('Identificador deve ser inteiro positivo.')
    return value


def fields(data, required, optional=()):
    if not isinstance(data, dict) or set(data) - set(required) - set(optional) or set(required) - set(data):
        raise ValueError('Campos financeiros inválidos ou incompletos.')
    return dict(data)


def amount(value, *, positive=False, scale=None):
    number = Decimal(decimal_text(value, positive=positive))
    if number < 0: raise ValueError('Montante não pode ser negativo.')
    if scale is not None:
        with localcontext() as ctx:
            ctx.prec = 64
            if number != number.quantize(Decimal(1).scaleb(-scale)):
                raise ValueError(f'Montante exige no máximo {scale} casas decimais; não há arredondamento implícito.')
    return number


def transaction(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            with localcontext() as context:
                context.prec = 64
                result = function(*args, **kwargs)
                db.session.commit()
                return result
        except ValueError as exc:
            db.session.rollback(); return Result(False, error=str(exc), code=422)
        except IntegrityError:
            db.session.rollback(); return Result(False, error='Conflito de referência, origem ou cadastro. Nenhuma duplicação confirmada.', code=409)
        except SQLAlchemyError:
            db.session.rollback(); return Result(False, error='Conflito de gravação. Atualize e tente novamente; nenhuma alteração confirmada.', code=409)
        except Exception:
            db.session.rollback(); raise
    return wrapped


def reserve(model, row_id):
    ident(row_id)
    db.session.execute(update(model).where(model.id == row_id).values(id=model.id).execution_options(synchronize_session=False))
    row = model.query.filter_by(id=row_id).populate_existing().first()
    if row is None: raise ValueError('Registro financeiro não encontrado.')
    return row


def catalog_row(model, row_id, org, *, direction=None, lock=True):
    row = reserve(model, row_id) if lock else db.session.get(model, ident(row_id), populate_existing=True)
    if row is None: raise ValueError('Cadastro financeiro não encontrado.')
    if row.organization_code != org or not row.is_active:
        raise ValueError('Cadastro ausente, inativo ou de outra organização.')
    if direction and row.direction != direction:
        raise ValueError('Categoria incompatível com pagar/receber.')
    return row


def post_cash(account, delta, operation_date, reference, snapshot, actor):
    if operation_date < account.opening_date:
        raise ValueError('Lançamento anterior à abertura da conta.')
    balance = account.balance + delta
    if balance < 0 or balance >= Decimal('1e18'):
        raise ValueError('Saldo da conta insuficiente ou fora da magnitude suportada.')
    before = canonical(account.balance)
    account.balance = balance
    movement = Movement(account_id=account.id, reference=reference, amount_delta=delta, balance_after=balance,
        operation_date=operation_date, snapshot_json=dump({**snapshot, 'organization_code': account.organization_code,
            'currency_code': account.currency_code, 'balance_before': before}), created_by=actor)
    db.session.add(movement); db.session.flush()
    return movement.to_dict()


@transaction
def create_catalog(kind, data, *, actor):
    actor = text(actor, 120, 'Autor')
    if kind not in CATALOGS: raise ValueError('Tipo de cadastro inválido.')
    required = {'organization_code', 'name'}
    if kind == 'accounts': required |= {'kind', 'opening_balance', 'opening_date', 'policy_version_id'}
    if kind == 'categories': required |= {'direction'}
    data = fields(data, required, {'bank_name', 'branch', 'account_number'} if kind == 'accounts' else ())
    org = resolve_organization_by_code(data['organization_code'])['code']
    name = text(data['name'], 100, 'Nome')
    model = CATALOGS[kind]
    values = dict(organization_code=org, name=name, created_by=actor)
    if kind == 'categories':
        if data['direction'] not in ('PAYABLE', 'RECEIVABLE'): raise ValueError('Escolha pagar ou receber.')
        values['direction'] = data['direction']
        resolve_selected_policy(org)
    elif kind == 'accounts':
        if data['kind'] not in ('BANK', 'CASH'): raise ValueError('Conta deve ser bancária ou caixa.')
        date_value = day(data['opening_date'])
        policy = resolve_selected_policy(org, policy_version_id=data['policy_version_id'], operation_date=data['opening_date'])
        opening = amount(data['opening_balance'], scale=policy['decimal_places'])
        values.update(kind=data['kind'], currency_code=policy['currency_code'], opening_date=date_value,
            balance=Decimal(0), opening_json=dump({'amount': canonical(opening), 'policy': policy, 'operation_date': data['opening_date']}))
        for key, limit in [('bank_name', 100), ('branch', 30), ('account_number', 40)]:
            values[key] = text(data[key], limit, key) if data.get(key) else None
        if data['kind'] == 'CASH' and any(values.get(key) for key in ('bank_name', 'branch', 'account_number')):
            raise ValueError('Caixa não utiliza dados bancários.')
    else:
        resolve_selected_policy(org)
    row = model(**values); db.session.add(row); db.session.flush()
    if kind == 'accounts':
        post_cash(row, opening, date_value, f'opening:{row.id}', {'opening': json.loads(row.opening_json)}, actor)
    return Result(True, data=row.to_dict(), code=201)


@transaction
def edit_catalog(kind, row_id, data, *, actor):
    text(actor, 120, 'Autor')
    if kind not in CATALOGS: raise ValueError('Tipo de cadastro inválido.')
    data = fields(data, {'expected_version', 'name', 'is_active'}, {'bank_name', 'branch', 'account_number'} if kind == 'accounts' else ())
    row = reserve(CATALOGS[kind], row_id)
    resolve_organization_by_code(row.organization_code)
    if type(data['expected_version']) is not int or data['expected_version'] != row.version:
        raise ValueError('Cadastro alterado por outra operação. Recarregue antes de editar.')
    if type(data['is_active']) is not bool: raise ValueError('Ativo deve ser booleano.')
    row.name = text(data['name'], 100, 'Nome'); row.is_active = data['is_active']; row.version += 1
    if kind == 'accounts':
        for key, limit in [('bank_name', 100), ('branch', 30), ('account_number', 40)]:
            if key in data: setattr(row, key, text(data[key], limit, key) if data[key] else None)
        if row.kind == 'CASH' and any(getattr(row, key) for key in ('bank_name', 'branch', 'account_number')):
            raise ValueError('Caixa não utiliza dados bancários.')
    return Result(True, data=row.to_dict())


def _schedule(total, source_scale, first_due, count, base_total, policy):
    if type(count) is not int or not 1 <= count <= 120: raise ValueError('Parcelas: inteiro de 1 a 120.')
    first = day(first_due); quantum = Decimal(1).scaleb(-source_scale)
    piece = (total / count).quantize(quantum, rounding=ROUND_DOWN)
    if piece <= 0: raise ValueError('Valor insuficiente para dividir nessa quantidade de parcelas.')
    result = []; used_original = used_base = Decimal(0)
    for index in range(count):
        original = total - used_original if index == count - 1 else piece
        base = base_total - used_base if index == count - 1 else min(base_total - used_base,
            (base_total * original / total).quantize(Decimal(1).scaleb(-policy['decimal_places']), rounding=ROUNDINGS[policy['rounding']]))
        month_index = first.month - 1 + index; year = first.year + month_index // 12; month = month_index % 12 + 1
        try: due = date(year, month, min(first.day, calendar.monthrange(year, month)[1]))
        except (ValueError, OverflowError): raise ValueError('Vencimento fora do calendário suportado.')
        result.append({'number': index + 1, 'due_date': due.isoformat(), 'amount': canonical(original), 'base_amount': canonical(base)})
        used_original += original; used_base += base
    return result


@transaction
def create_title(data, *, actor, preview=False):
    actor = text(actor, 120, 'Autor')
    data = fields(data, {'organization_code', 'kind', 'reference', 'counterparty', 'currency_code', 'amount',
        'issue_date', 'first_due', 'installment_count', 'category_id', 'cost_center_id', 'rate_id', 'policy_version_id',
        'idempotency_key'}, {'purchase_order_id'})
    org = resolve_organization_by_code(data['organization_code'])['code']
    if data['kind'] not in ('PAYABLE', 'RECEIVABLE'): raise ValueError('Escolha pagar ou receber.')
    issue = day(data['issue_date']); due = day(data['first_due'])
    if due < issue: raise ValueError('Primeiro vencimento anterior à emissão.')
    for key in ('category_id', 'cost_center_id'): data[key] = ident(data[key])
    for key in ('rate_id', 'policy_version_id', 'purchase_order_id'): data[key] = ident(data.get(key), optional=True)
    data['organization_code'] = org
    data['reference'] = text(data['reference'], 120, 'Referência')
    data['counterparty'] = text(data['counterparty'], 200, 'Fornecedor/cliente')
    data['idempotency_key'] = text(data['idempotency_key'], 80, 'Chave de idempotência')
    data['amount'] = canonical(amount(data['amount'], positive=True))
    request_json = dump(data)
    previous = Title.query.filter_by(organization_code=org, idempotency_key=data['idempotency_key']).first()
    if previous:
        if previous.request_json != request_json: raise ValueError('Referência de título usada com outros dados.')
        return Result(True, data=title_detail(previous.id), code=200)
    category = catalog_row(Category, data['category_id'], org, direction=data['kind'], lock=not preview)
    center = catalog_row(Center, data['cost_center_id'], org, lock=not preview)
    previous = Title.query.filter_by(organization_code=org, idempotency_key=data['idempotency_key']).populate_existing().first()
    if previous:
        if previous.request_json != request_json: raise ValueError('Referência de título usada com outros dados.')
        return Result(True, data=title_detail(previous.id))
    source = None
    if data['purchase_order_id'] is not None:
        from .treasury_purchase_contract import purchase_obligation
        source = purchase_obligation(data['purchase_order_id'], reserve=not preview)
        if data['kind'] != 'PAYABLE' or source['organization_code'] != org or source['currency_code'] != data['currency_code'] or Decimal(source['amount']) != Decimal(data['amount']):
            raise ValueError('Título diverge da organização, moeda ou total congelado do pedido.')
        if data['counterparty'] != source['counterparty']:
            raise ValueError('Fornecedor do título diverge do pedido.')
    conversion = preview_conversion({'organization_code': org, 'source_currency': data['currency_code'],
        'amount': data['amount'], 'operation_date': data['issue_date'], 'rate_id': data['rate_id'], 'policy_version_id': data['policy_version_id']})
    currency = db.session.get(Currency, data['currency_code'])
    scale = conversion['policy']['decimal_places'] if data['currency_code'] == conversion['target_currency'] else currency.decimal_places
    total = amount(data['amount'], positive=True)
    if source:
        total = total.quantize(Decimal(1).scaleb(-scale), rounding=ROUNDINGS[conversion['policy']['rounding']])
        if total <= 0: raise ValueError('Total arredondado do pedido não constitui obrigação positiva.')
        conversion = preview_conversion({'organization_code': org, 'source_currency': data['currency_code'],
            'amount': canonical(total), 'operation_date': data['issue_date'], 'rate_id': data['rate_id'], 'policy_version_id': data['policy_version_id']})
    else:
        total = amount(data['amount'], positive=True, scale=scale)
    installments = _schedule(total, scale, data['first_due'], data['installment_count'], Decimal(conversion['converted_amount']), conversion['policy'])
    snapshot = {'conversion': conversion, 'source_scale': scale, 'category': category.to_dict(), 'cost_center': center.to_dict(),
                'purchase': source, 'installments': installments,
                'original_amount': data['amount'], 'rounded_original_amount': canonical(total)}
    if preview:
        return Result(True, data={'organization_code': org, 'currency_code': data['currency_code'],
            'amount': canonical(total), 'base_amount': conversion['converted_amount'], 'snapshot': snapshot})
    row = Title(organization_code=org, kind=data['kind'], reference=data['reference'], counterparty=data['counterparty'],
        currency_code=data['currency_code'], amount=total, base_amount=Decimal(conversion['converted_amount']), issue_date=issue,
        category_id=category.id, cost_center_id=center.id, source_reference=f'purchase:{data["purchase_order_id"]}' if source else None,
        idempotency_key=data['idempotency_key'], request_json=request_json, snapshot_json=dump(snapshot), created_by=actor)
    db.session.add(row); db.session.flush()
    for item in installments:
        db.session.add(Installment(title_id=row.id, number=item['number'], due_date=day(item['due_date']),
            amount=Decimal(item['amount']), base_amount=Decimal(item['base_amount'])))
    db.session.flush()
    return Result(True, data=title_detail(row.id), code=201)


def active_settlements(installment_id):
    return Settlement.query.outerjoin(Reversal, Reversal.settlement_id == Settlement.id).filter(
        Settlement.installment_id == installment_id, Reversal.id.is_(None)).order_by(Settlement.id).all()


def installment_detail(row):
    active = active_settlements(row.id)
    with localcontext() as ctx:
        ctx.prec = 64
        remaining = row.amount - sum((item.principal for item in active), Decimal(0))
        carrying = row.base_amount - sum((item.carrying_base for item in active), Decimal(0))
    return {**row.to_dict(), 'remaining': canonical(remaining), 'carrying_remaining': canonical(carrying),
            'status': 'PAID' if remaining == 0 else 'PARTIAL' if active else 'OPEN'}


def title_detail(row_id):
    row = db.session.get(Title, ident(row_id), populate_existing=True)
    if row is None: raise ValueError('Título não encontrado.')
    cancellation = db.session.get(Cancellation, row_id)
    installments = [installment_detail(item) for item in Installment.query.filter_by(title_id=row.id).order_by(Installment.number).all()]
    with localcontext() as ctx:
        ctx.prec = 64
        remaining = sum((Decimal(item['remaining']) for item in installments), Decimal(0))
    settled = Settlement.query.join(Installment).filter(Installment.title_id == row.id).order_by(Settlement.id).all()
    details = []
    for item in settled:
        reversal = Reversal.query.filter_by(settlement_id=item.id).first()
        details.append({**item.to_dict(), 'reversal': reversal.to_dict() if reversal else None})
    base_remaining = sum((Decimal(item['carrying_remaining']) for item in installments), Decimal(0))
    return {**row.to_dict(), 'installments': installments, 'remaining': canonical(remaining), 'base_remaining': canonical(base_remaining),
            'status': 'CANCELLED' if cancellation else 'PAID' if remaining == 0 else 'PARTIAL' if remaining < row.amount else 'OPEN',
            'cancellation': cancellation.to_dict() if cancellation else None, 'settlements': details}


@transaction
def settle(installment_id, data, *, actor, preview=False):
    actor = text(actor, 120, 'Autor')
    data = fields(data, {'account_id', 'principal', 'interest', 'fine', 'discount', 'operation_date', 'rate_id',
                         'policy_version_id', 'idempotency_key', 'notes'})
    ident(installment_id); data['account_id'] = ident(data['account_id'])
    for key in ('rate_id', 'policy_version_id'): data[key] = ident(data[key], optional=True)
    date_value = day(data['operation_date']); data['idempotency_key'] = text(data['idempotency_key'], 80, 'Referência da baixa')
    data['notes'] = text(data['notes'], 1000, 'Observações') if data['notes'] else None
    installment = db.session.get(Installment, installment_id)
    if installment is None: raise ValueError('Parcela não encontrada.')
    title = db.session.get(Title, installment.title_id, populate_existing=True) if preview else reserve(Title, installment.title_id)
    snapshot = json.loads(title.snapshot_json); scale = snapshot['source_scale']
    for field in ('principal', 'interest', 'fine', 'discount'):
        data[field] = canonical(amount(data[field], positive=field == 'principal', scale=scale))
    requested = dump({'installment_id': installment_id, **data})
    previous = Settlement.query.filter_by(organization_code=title.organization_code, idempotency_key=data['idempotency_key']).first()
    if previous:
        if previous.request_json != requested: raise ValueError('Referência de baixa usada com outros dados.')
        return Result(True, data=settlement_detail(previous), code=200)
    resolve_organization_by_code(title.organization_code)
    if db.session.get(Cancellation, title.id): raise ValueError('Título cancelado não pode ser liquidado.')
    if date_value < title.issue_date: raise ValueError('Baixa anterior à emissão do título.')
    account = catalog_row(Account, data['account_id'], title.organization_code, lock=not preview)
    current = installment_detail(installment)
    principal = Decimal(data['principal']); discount = Decimal(data['discount'])
    if principal > Decimal(current['remaining']): raise ValueError('Principal excede o saldo aberto da parcela.')
    if discount > principal: raise ValueError('Desconto não pode superar o principal liquidado.')
    cash = principal + Decimal(data['interest']) + Decimal(data['fine']) - discount
    conversion_data = {'organization_code': title.organization_code, 'source_currency': title.currency_code,
        'operation_date': data['operation_date'], 'rate_id': data['rate_id'], 'policy_version_id': data['policy_version_id']}
    conversions = {name: preview_conversion({**conversion_data, 'amount': canonical(value)}) for name, value in
        [('cash', cash), ('principal', principal), ('interest', Decimal(data['interest'])), ('fine', Decimal(data['fine'])), ('discount', discount)]}
    policy = conversions['cash']['policy']; cash_base = Decimal(conversions['cash']['converted_amount'])
    if account.currency_code != policy['currency_code']: raise ValueError('Conta não opera na moeda-base do título.')
    carrying = Decimal(current['carrying_remaining']) if principal == Decimal(current['remaining']) else min(Decimal(current['carrying_remaining']),
        (installment.base_amount * principal / installment.amount).quantize(Decimal(1).scaleb(-policy['decimal_places']), rounding=ROUNDINGS[policy['rounding']]))
    principal_base = Decimal(conversions['principal']['converted_amount'])
    components = {key: Decimal(conversions[key]['converted_amount']) for key in ('interest', 'fine', 'discount')}
    residual = cash_base - (principal_base + components['interest'] + components['fine'] - components['discount'])
    frozen = {'currency_code': title.currency_code, 'base_currency': policy['currency_code'], 'kind': title.kind,
        'reference': title.reference, 'conversions': conversions, 'carrying_base': canonical(carrying),
        'exchange_difference': canonical(principal_base - carrying), 'rounding_difference': canonical(residual),
        'account': {'id': account.id, 'name': account.name}, 'category': snapshot['category'], 'cost_center': snapshot['cost_center']}
    if date_value < account.opening_date:
        raise ValueError('Lançamento anterior à abertura da conta.')
    after = account.balance + (-cash_base if title.kind == 'PAYABLE' else cash_base)
    if after < 0 or after >= Decimal('1e18'):
        raise ValueError('Saldo da conta insuficiente ou fora da magnitude suportada.')
    if preview:
        return Result(True, data={**frozen, 'principal': canonical(principal), 'cash_base': canonical(cash_base), 'balance_after': canonical(after)})
    row = Settlement(organization_code=title.organization_code, installment_id=installment_id, account_id=account.id,
        principal=principal, carrying_base=carrying, cash_base=cash_base, operation_date=date_value,
        idempotency_key=data['idempotency_key'], request_json=requested, snapshot_json=dump(frozen), created_by=actor)
    db.session.add(row); db.session.flush()
    post_cash(account, -cash_base if title.kind == 'PAYABLE' else cash_base, date_value,
              f'settlement:{row.id}', {'settlement_id': row.id, 'title_id': title.id, **frozen}, actor)
    return Result(True, data=row.to_dict(), code=201)


@transaction
def reverse(settlement_id, data, *, actor):
    actor = text(actor, 120, 'Autor')
    data = fields(data, {'reason', 'operation_date', 'idempotency_key'})
    data['reason'] = text(data['reason'], 1000, 'Motivo'); data['idempotency_key'] = text(data['idempotency_key'], 80, 'Referência de estorno')
    date_value = day(data['operation_date'])
    settlement = db.session.get(Settlement, ident(settlement_id))
    if settlement is None: raise ValueError('Baixa não encontrada.')
    installment = db.session.get(Installment, settlement.installment_id)
    title = reserve(Title, installment.title_id)
    previous = Reversal.query.filter_by(organization_code=title.organization_code, idempotency_key=data['idempotency_key']).first()
    if previous:
        if previous.settlement_id != settlement_id or previous.reason != data['reason'] or previous.operation_date != date_value:
            raise ValueError('Referência de estorno usada com outros dados.')
        return Result(True, data=previous.to_dict())
    if Reversal.query.filter_by(settlement_id=settlement_id).first(): raise ValueError('Baixa já estornada.')
    resolve_organization_by_code(title.organization_code)
    if date_value < settlement.operation_date: raise ValueError('Estorno anterior à baixa original.')
    from .accrual_service import assert_source_unrecognized
    assert_source_unrecognized(f'settlement:{settlement.id}:',prefix=True)
    account = reserve(Account, settlement.account_id)
    row = Reversal(settlement_id=settlement_id, organization_code=title.organization_code, operation_date=date_value,
        reason=data['reason'], idempotency_key=data['idempotency_key'], created_by=actor)
    db.session.add(row); db.session.flush()
    movement = Movement.query.filter_by(account_id=account.id, reference=f'settlement:{settlement.id}').one()
    post_cash(account, -movement.amount_delta, date_value, f'reversal:{row.id}',
        {'reversal_id': row.id, 'settlement_id': settlement.id, 'title_id': title.id,
         'reason': data['reason'], 'original_movement': movement.to_dict()}, actor)
    return Result(True, data=row.to_dict(), code=201)


@transaction
def cancel_title(title_id, data, *, actor):
    actor = text(actor, 120, 'Autor'); data = fields(data, {'reason'}); reason = text(data['reason'], 1000, 'Motivo')
    title = reserve(Title, title_id)
    previous = db.session.get(Cancellation, title_id)
    if previous:
        if previous.reason != reason: raise ValueError('Título já cancelado com outro motivo.')
        return Result(True, data=previous.to_dict())
    resolve_organization_by_code(title.organization_code)
    if any(active_settlements(item.id) for item in Installment.query.filter_by(title_id=title_id).all()):
        raise ValueError('Estorne as baixas ativas antes de cancelar o título.')
    from .accrual_service import assert_source_unrecognized
    assert_source_unrecognized(f'title:{title_id}')
    row = Cancellation(title_id=title_id, reason=reason, created_by=actor); db.session.add(row); db.session.flush()
    return Result(True, data=row.to_dict(), code=201)


def preview_settlement(installment_id, data, *, actor):
    """Mesma avaliação da baixa, sem UPDATE, flush, commit ou reserva de saldo."""
    try:
        with db.session.no_autoflush, localcontext() as ctx:
            ctx.prec = 64
            return settle.__wrapped__(installment_id, data, actor=actor, preview=True)
    except ValueError as exc:
        return Result(False, error=str(exc), code=422)


def preview_title(data, *, actor):
    """Avalia documento e parcelas sem confirmar título nem tocar no estoque."""
    try:
        with db.session.no_autoflush, localcontext() as ctx:
            ctx.prec = 64
            return create_title.__wrapped__(data, actor=actor, preview=True)
    except ValueError as exc:
        return Result(False, error=str(exc), code=422)


def settlement_detail(row):
    reversal = Reversal.query.filter_by(settlement_id=row.id).first()
    return {**row.to_dict(), 'status': 'REVERSED' if reversal else 'POSTED',
            'reversal': reversal.to_dict() if reversal else None}
