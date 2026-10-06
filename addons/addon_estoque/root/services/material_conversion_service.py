"""Conversões públicas por material. Extensão manual; não movimenta estoque."""
from math import isfinite
from core.db import db
from sqlalchemy import update
from services.core.i18n_service import translate as t
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
from addons.addon_estoque.root.model.unidade_catalogo import UnidadeCatalogo


def normalizar_unidade(value):
    code = (value or "").strip().upper()
    return {"ITEMS": "ITEM"}.get(code, code)


def _rows(material_id, code):
    return [row for row in MaterialUnidade.query.filter_by(material_id=material_id, is_deleted=False).all()
            if normalizar_unidade(row.unidade) == code]


def obter_fator(material_id, origem, destino):
    """Consulta sem escrita; só usa linhas únicas, ativas e fatores válidos."""
    rows = [_rows(material_id, normalizar_unidade(unit)) for unit in (origem, destino)]
    if any(len(group) != 1 for group in rows):
        return None
    source, target = (group[0] for group in rows)
    if any(not row.ativo or row.fator_para_base is None or not isfinite(row.fator_para_base) or row.fator_para_base <= 0
           for row in (source, target)):
        return None
    factor = source.fator_para_base / target.fator_para_base
    return factor if isfinite(factor) and factor > 0 else None


def cadastrar_conversao(material_id, origem, fator, *, unidade_base_esperada, commit=True):
    """Adiciona unidade de consumo. Nunca troca base nem sobrescreve fator existente.

    ITEM é incluído no catálogo somente mediante este cadastro explícito.
    Base legada sem MaterialUnidade é registrada com fator 1 e o mesmo código.
    A transação inclui catálogo/base/conversão; qualquer falha desfaz tudo.
    """
    try:
        # Reserva escrita no SQLite antes de verificar/criar unidades.
        db.session.execute(update(Material).where(Material.id == material_id).values(
            updated_at=Material.updated_at).execution_options(synchronize_session=False))
        material = Material.query.filter_by(id=material_id, is_deleted=False, ativo=True).first()
        if material is None:
            raise ValueError(t("estoque.conversion.material_unavailable"))
        bases = MaterialUnidade.query.filter_by(material_id=material_id, is_deleted=False, is_unidade_base=True).all()
        if len(bases) > 1 or (bases and not bases[0].ativo):
            raise ValueError(t("estoque.conversion.invalid_base"))
        base = normalizar_unidade(bases[0].unidade if bases else material.unidade_medida)
        if not base or base != normalizar_unidade(unidade_base_esperada):
            raise ValueError(t("estoque.conversion.stale_base"))
        if bases and bases[0].fator_para_base != 1:
            raise ValueError(t("estoque.conversion.invalid_base"))
        code = normalizar_unidade(origem)
        if not code or code == base:
            raise ValueError(t("estoque.conversion.same_unit"))
        if isinstance(fator, bool):
            raise ValueError(t("estoque.conversion.invalid_factor"))
        try:
            factor = float(str(fator).replace(",", "."))
        except (ValueError, TypeError):
            raise ValueError(t("estoque.conversion.invalid_factor")) from None
        if not isfinite(factor) or factor <= 0:
            raise ValueError(t("estoque.conversion.invalid_factor"))
        base_catalog = UnidadeCatalogo.query.filter_by(codigo=base, is_deleted=False).first()
        if base_catalog is None:
            raise ValueError(t("estoque.conversion.invalid_base"))
        source_catalog = UnidadeCatalogo.query.filter_by(codigo=code).first()
        if source_catalog is None and code == "ITEM":
            source_catalog = UnidadeCatalogo(codigo="ITEM", descricao="Item", dimensao="contagem", fator_referencia=None)
            db.session.add(source_catalog)
        if source_catalog is None or source_catalog.is_deleted:
            raise ValueError(t("estoque.conversion.unknown_unit"))
        existing = _rows(material_id, code)
        if existing:
            if len(existing) != 1 or not existing[0].ativo or existing[0].tipo_uso not in ("consumo", "ambos") or existing[0].fator_para_base != factor:
                raise ValueError(t("estoque.conversion.existing_conflict"))
            row = existing[0]
        else:
            row = MaterialUnidade(material_id=material_id, unidade=code, fator_para_base=factor,
                                 is_unidade_base=False, tipo_uso="consumo", ativo=True)
            db.session.add(row)
        if not bases:
            matches = _rows(material_id, base)
            if matches:
                raise ValueError(t("estoque.conversion.invalid_base"))
            db.session.add(MaterialUnidade(material_id=material_id, unidade=base, fator_para_base=1,
                                          is_unidade_base=True, tipo_uso="ambos", ativo=True))
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return row.to_dict()
    except Exception:
        db.session.rollback()
        raise
