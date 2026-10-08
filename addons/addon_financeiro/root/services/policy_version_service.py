"""Versionamento explícito: a configuração inicial continua sendo a versão 1."""
import logging
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from core.db import db
from services.core.organization_service import Result
from addons.addon_financeiro.root.model.policy_version import MonetaryPolicyVersion
from .monetary_service import resolve_policy, ROUNDINGS

logger = logging.getLogger(__name__)


def create_policy_version(data, *, actor):
    from .exchange_service import text, day
    try:
        required = {'organization_code', 'expected_version', 'decimal_places', 'rounding', 'valid_from', 'reason'}
        if not isinstance(data, dict) or set(data) != required:
            raise ValueError('Informe organização, versão anterior esperada, casas, arredondamento, data e motivo.')
        initial = resolve_policy(data['organization_code'])
        expected = data['expected_version']
        if type(expected) is not int or expected < 1:
            raise ValueError('Versão anterior esperada deve ser inteiro positivo.')
        scale = data['decimal_places']
        if type(scale) is not int or not 0 <= scale <= 6:
            raise ValueError('Casas decimais: inteiro de zero a seis.')
        rounding = data['rounding']
        if not isinstance(rounding, str) or rounding not in ROUNDINGS:
            raise ValueError('Escolha HALF_UP ou HALF_EVEN explicitamente.')
        valid_from = day(data['valid_from'])
        reason = text(data['reason'], 200, 'Motivo')
        actor = text(actor, 120, 'Autor')
        latest = (MonetaryPolicyVersion.query.filter_by(policy_id=initial['id'])
                  .order_by(MonetaryPolicyVersion.version_number.desc()).populate_existing().first())
        actual = latest.version_number if latest else 1
        if expected != actual:
            return Result(False, error=f'Política alterada por outro cadastro. Última versão: {actual}. Recarregue e revise.', code=409)
        if latest and valid_from < latest.valid_from:
            raise ValueError('Data não pode anteceder a última versão cadastrada.')
        previous_scale = latest.decimal_places if latest else initial['decimal_places']
        previous_rounding = latest.rounding if latest else initial['rounding']
        if (scale, rounding) == (previous_scale, previous_rounding):
            raise ValueError('A nova versão deve alterar casas decimais ou arredondamento.')
        obj = MonetaryPolicyVersion(policy_id=initial['id'], version_number=actual + 1,
                                    decimal_places=scale, rounding=rounding, valid_from=valid_from,
                                    reason=reason, created_by=actor)
        db.session.add(obj)
        db.session.commit()
        return Result(True, data=obj.to_dict(), code=201)
    except ValueError as exc:
        return Result(False, error=str(exc), code=422)
    except IntegrityError:
        db.session.rollback()
        return Result(False, error='Outra versão foi cadastrada simultaneamente. Recarregue e revise.', code=409)
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception('Falha ao cadastrar versão monetária')
        return Result(False, error='Falha ao salvar versão; nenhuma alteração confirmada.', code=409)


def resolve_selected_policy(organization_code, *, policy_version_id=None, operation_date=None):
    """Sem ID retorna exatamente o DTO legado; ID explícito exige data da operação."""
    initial = resolve_policy(organization_code)
    if policy_version_id is None:
        return initial
    if type(policy_version_id) is not int or policy_version_id <= 0:
        raise ValueError('ID de versão deve ser inteiro positivo ou null para política inicial.')
    version = db.session.get(MonetaryPolicyVersion, policy_version_id, populate_existing=True)
    if version is None or version.policy_id != initial['id']:
        raise ValueError('Versão não pertence à organização solicitada.')
    from .exchange_service import day
    operation_day = day(operation_date)
    if operation_day < version.valid_from:
        raise ValueError('Versão ainda não válida na data da operação.')
    return initial | {
        'decimal_places': version.decimal_places, 'rounding': version.rounding,
        'version_id': version.id, 'version_number': version.version_number,
        'valid_from': version.valid_from.isoformat(), 'reason': version.reason,
        'created_by': version.created_by, 'version_created_at': version.created_at.isoformat()}
