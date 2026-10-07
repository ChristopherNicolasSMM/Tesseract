"""Manutenção manual de conversões: sem reinterpretar saldos ou históricos."""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
import logging
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, OperationalError

from core.db import db
from core.reference_usage import has_declared_references
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
from addons.addon_estoque.root.model.unidade_catalogo import UnidadeCatalogo

logger = logging.getLogger(__name__)


@dataclass
class Result:
    success: bool
    data: object = None
    error: str | None = None
    code: int = 200


class UnitRuleError(ValueError):
    def __init__(self, message, code=422):
        super().__init__(message)
        self.code = code


def normalize(value):
    if not isinstance(value, str):
        return ''
    code = value.strip().upper()
    return {'ITEMS': 'ITEM'}.get(code, code)


def reserve_material(ident, *, include_deleted=False):
    """Mesma linha reservada pela movimentação central; não confirma transação."""
    if not isinstance(ident, int) or isinstance(ident, bool) or ident <= 0:
        raise UnitRuleError('Selecione um material válido.')
    with db.session.no_autoflush:
        db.session.execute(update(Material).where(Material.id == ident).values(
            updated_at=Material.updated_at).execution_options(synchronize_session=False))
        material = Material.query.filter_by(id=ident).populate_existing().first()
    if material is None or (material.is_deleted and not include_deleted):
        raise UnitRuleError('Material ausente ou na lixeira.')
    return material


def _rows(material_id):
    return MaterialUnidade.query.filter_by(material_id=material_id).populate_existing().all()


def _used(material):
    # Inclui ledger/saldo/composição/compras e referências fracas declaradas
    # de módulos carregados (receitas inclusive), sem importar models externos.
    return has_declared_references('materials', material.to_dict(), exclude_models=(MaterialUnidade,))


def _unit_refs(obj):
    return has_declared_references('material_unidades', obj.to_dict())


def _validate(obj, material, rows):
    code = normalize(obj.unidade)
    if not code or not UnidadeCatalogo.query.filter_by(codigo=code, is_deleted=False).first():
        raise UnitRuleError('Selecione uma unidade ativa do catálogo; conteúdo de PCT pertence ao fator do material.')
    obj.unidade = code
    factor = obj.fator_para_base
    if isinstance(factor, bool) or not isinstance(factor, (int, float)) or not isfinite(factor) or factor <= 0:
        raise UnitRuleError('O fator para a unidade-base deve ser positivo e finito.')
    if obj.is_unidade_base and factor != 1:
        raise UnitRuleError('A unidade-base deve ter fator igual a 1.')
    if obj.tipo_uso not in ('compra', 'consumo', 'ambos'):
        raise UnitRuleError('Tipo de uso inválido.')
    if not isinstance(obj.ativo, bool) or not isinstance(obj.is_unidade_base, bool):
        raise UnitRuleError('Estado de unidade inválido.')
    for row in rows:
        if row.id == obj.id or row.is_deleted:
            continue
        if normalize(row.unidade) == code:
            raise UnitRuleError('Já existe conversão não arquivada com esse código para o material.', 409)
        if obj.is_unidade_base and row.is_unidade_base:
            raise UnitRuleError('Já existe unidade-base não arquivada para o material.', 409)


def _base_guard(obj, material, rows, before):
    others = [row for row in rows if row.id != obj.id]
    registered = [row for row in rows if row.is_unidade_base and not row.is_deleted]
    if len(registered) > 1:
        raise UnitRuleError('Cadastro possui bases conflitantes. Revise antes de manter conversões.', 409)
    # A consulta é feita antes de aplicar campos, para não perder o estado antigo.
    changing = before is not None and (normalize(before['unidade']) != obj.unidade
                                      or before['is_unidade_base'] != obj.is_unidade_base)
    was_base = bool(before and before['is_unidade_base'])
    previous_base = normalize(material.unidade_medida)
    if not previous_base:
        previous_base = normalize(before['unidade']) if was_base else (normalize(registered[0].unidade) if registered else '')
    if was_base and not obj.is_unidade_base:
        raise UnitRuleError('Não desmarque a base isoladamente. Preserve-a ou arquive uma base sem uso antes de cadastrar outra.', 409)
    if not obj.is_unidade_base:
        if not previous_base:
            raise UnitRuleError('Defina a unidade-base antes de cadastrar/manter uma conversão.')
        if registered and (not registered[0].ativo or registered[0].fator_para_base != 1
                           or normalize(registered[0].unidade) != previous_base):
            raise UnitRuleError('Unidade-base inconsistente ou inativa; preserve os dados e revise a configuração.', 409)
    if obj.is_unidade_base:
        intended_change = (changing or (previous_base != obj.unidade))
        # Completar o espelho vazio da mesma base já registrada não é troca.
        if not previous_base and was_base and normalize(before['unidade']) == obj.unidade:
            intended_change = False
        if intended_change and (_used(material) or others):
            raise UnitRuleError('Troca de base bloqueada: existem uso/histórico ou outras conversões. Não reinterpretar saldos e fatores.', 409)
        if previous_base and previous_base != obj.unidade and others:
            raise UnitRuleError('Preserve a base das conversões existentes.', 409)


def validate_new_unit(obj, material, rows):
    """Contrato comum ao CRUD e ao cadastro explícito público, sem commit."""
    _validate(obj, material, rows)
    _base_guard(obj, material, rows, None)


def maintain_material(action, ident):
    """Pais não desaparecem enquanto conversões/referências dependerem deles."""
    try:
        obj = reserve_material(ident, include_deleted=True)
        if action == 'restore':
            if not obj.is_deleted:
                raise UnitRuleError('Não está na lixeira.', 400)
            obj.is_deleted, obj.deleted_at = False, None
        else:
            if has_declared_references('materials', obj.to_dict()):
                raise UnitRuleError('Material possui conversões ou referências históricas. Preserve o cadastro; use a inativação quando necessário.', 409)
            if action == 'trash':
                if obj.is_deleted:
                    raise UnitRuleError('Já está na lixeira.', 400)
                obj.is_deleted, obj.deleted_at = True, datetime.now(timezone.utc)
            elif action == 'delete_permanent':
                if not obj.is_deleted:
                    raise UnitRuleError('Apenas registros na lixeira podem ser excluídos permanentemente.', 400)
                db.session.delete(obj)
            else:
                raise UnitRuleError('Operação inválida.')
        db.session.commit()
        return Result(True, data={'id': ident} if action == 'delete_permanent' else obj)
    except UnitRuleError as exc:
        db.session.rollback()
        return Result(False, error=str(exc), code=exc.code)
    except (IntegrityError, OperationalError):
        db.session.rollback()
        return Result(False, error='Conflito com referência ou operação concorrente. Nenhuma alteração foi confirmada.', code=409)
    except Exception:
        db.session.rollback()
        logger.exception('Falha de manutenção de material %s', action)
        return Result(False, error='Não foi possível salvar. Nenhuma alteração foi confirmada.', code=422)


def operate(action, ident=None, data=None):
    """Override único para formulário/API e manutenção, com rollback amigável."""
    try:
        if action == 'create':
            if not isinstance(data, dict):
                raise UnitRuleError('Dados inválidos.')
            raw_id = data.get('material_id')
            if isinstance(raw_id, bool):
                raise UnitRuleError('Material inválido.')
            try:
                mid = int(raw_id)
            except (TypeError, ValueError):
                raise UnitRuleError('Selecione um material válido.') from None
            if isinstance(raw_id, float) and raw_id != mid:
                raise UnitRuleError('Material inválido.')
            material = reserve_material(mid)
            obj, before = MaterialUnidade(), None
        else:
            obj = db.session.get(MaterialUnidade, ident)
            if obj is None:
                raise UnitRuleError('Registro não encontrado.', 404)
            material = reserve_material(obj.material_id)
            obj = MaterialUnidade.query.filter_by(id=ident).populate_existing().first()
            if obj is None:
                raise UnitRuleError('Registro não encontrado.', 404)
            before = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        rows = _rows(material.id)
        if action in ('create', 'update'):
            if action == 'update' and obj.is_deleted:
                raise UnitRuleError('Não é possível editar um registro na lixeira.', 400)
            if not material.ativo:
                raise UnitRuleError('Material inativo; reative antes de configurar unidades.')
            if not isinstance(data, dict):
                raise UnitRuleError('Dados inválidos.')
            fields = {k: v for k, v in data.items() if k in MaterialUnidade.__table__.columns}
            if any(isinstance(fields.get(f), bool) for f in ('material_id', 'fator_para_base')):
                raise UnitRuleError('Material/fator não podem ser valores booleanos.')
            from .material_unidade_service import MaterialUnidadeService
            with db.session.no_autoflush:
                MaterialUnidadeService()._apply_fields(obj, fields)
                if before is None:
                    obj.material_id = material.id
                    obj.is_unidade_base = obj.is_unidade_base if obj.is_unidade_base is not None else False
                    obj.ativo = obj.ativo if obj.ativo is not None else True
                    obj.tipo_uso = obj.tipo_uso or 'ambos'
                elif obj.material_id != before['material_id']:
                    raise UnitRuleError('Conversão existente não pode mudar de material.', 409)
                _validate(obj, material, rows)
                # Reconsultas da coleção não podem apagar alterações do objeto.
                if before:
                    semantic_fields = ('unidade', 'fator_para_base', 'is_unidade_base', 'ativo', 'tipo_uso')
                    changed = any((normalize(before[f]) if f == 'unidade' else before[f]) != getattr(obj, f)
                                  for f in semantic_fields)
                    if changed and (_used(material) or _unit_refs(obj)):
                        raise UnitRuleError('Material/conversão possui uso ou referência histórica. Preserve fatores e identidade; nenhuma quantidade será convertida retroativamente.', 409)
                _base_guard(obj, material, rows, before)
                if obj.is_unidade_base:
                    material.unidade_medida = obj.unidade
            if action == 'create':
                db.session.add(obj)
        elif action in ('trash', 'restore', 'delete_permanent'):
            if action != 'restore' and (_used(material) or _unit_refs(obj)):
                raise UnitRuleError('Material/conversão possui uso ou referência histórica; preserve o registro.', 409)
            if action == 'trash':
                if obj.is_deleted:
                    raise UnitRuleError('Já está na lixeira.', 400)
                if obj.is_unidade_base and any(r.id != obj.id for r in rows):
                    raise UnitRuleError('Preserve a base enquanto existem outras conversões, inclusive arquivadas.', 409)
                obj.is_deleted, obj.deleted_at = True, datetime.now(timezone.utc)
                if obj.is_unidade_base:
                    material.unidade_medida = None
            elif action == 'restore':
                if not obj.is_deleted:
                    raise UnitRuleError('Não está na lixeira.', 400)
                if not material.ativo:
                    raise UnitRuleError('Reative o material antes de restaurar a unidade.')
                with db.session.no_autoflush:
                    _validate(obj, material, rows)
                    _base_guard(obj, material, rows, before)
                    if not obj.is_unidade_base:
                        base = normalize(material.unidade_medida)
                        if not base:
                            raise UnitRuleError('Restaure/defina a base antes da conversão.')
                    obj.is_deleted, obj.deleted_at = False, None
                    if obj.is_unidade_base:
                        material.unidade_medida = obj.unidade
            else:
                if not obj.is_deleted:
                    raise UnitRuleError('Apenas registros na lixeira podem ser excluídos permanentemente.', 400)
                db.session.delete(obj)
        else:
            raise UnitRuleError('Operação inválida.')
        db.session.commit()
        return Result(True, data={'id': ident} if action == 'delete_permanent' else obj,
                      code=201 if action == 'create' else 200)
    except UnitRuleError as exc:
        db.session.rollback()
        return Result(False, error=str(exc), code=exc.code)
    except (ValueError, TypeError, IntegrityError):
        db.session.rollback()
        return Result(False, error='Dados inválidos ou conflito com registro relacionado. Nenhuma alteração foi confirmada.', code=422)
    except OperationalError:
        db.session.rollback()
        return Result(False, error='Operação concorrente ou banco indisponível. Atualize e tente novamente.', code=409)
    except Exception:
        db.session.rollback()
        logger.exception('Falha de manutenção de unidade %s', action)
        return Result(False, error='Não foi possível salvar. Nenhuma alteração foi confirmada.', code=422)
