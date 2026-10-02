"""Base pública interna de rateio de volume e unidades do envase (leitura)."""
from math import isclose, isfinite

from addons.addon_brewstation.features.feature_envase.model.envase import Envase
from addons.addon_estoque.root.services import material_lookup


def positive_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
        raise ValueError(f'{label} deve ser positivo e finito; confira o histórico.')
    return float(value)


def volume_rateio(envase):
    """Regra existente: litros do envase / soma dos envases registrados ativos."""
    active = Envase.query.filter_by(lote_id=envase.lote_id, is_deleted=False, status='registrado').order_by(Envase.id).all()
    volumes = [positive_number(row.quantidade_litros, f'Volume do envase #{row.id}') for row in active]
    total = sum(volumes)
    positive_number(total, 'Volume registrado do lote')
    selected = positive_number(envase.quantidade_litros, 'Volume do envase selecionado')
    if envase.status != 'registrado' or envase.is_deleted or envase.id not in {row.id for row in active}:
        raise ValueError('Envase não integra a base de rateio registrada.')
    return {'volume_envase_litros': selected, 'volume_registrado_lote_litros': total,
            'fator_rateio': selected / total,
            'envases_base': [{'envase_id': row.id, 'litros': volume} for row, volume in zip(active, volumes)]}


def unit_basis(envase):
    """Snapshot novo é autoritativo; legado só estima pelo volume atual explícito."""
    snapshot = envase.producao_snapshot
    if snapshot is not None:
        if not isinstance(snapshot, dict):
            raise ValueError('Snapshot de produção inválido; confira o histórico.')
        volume = positive_number(snapshot.get('volume_por_unidade_litros'), 'Volume por unidade registrado')
        units = positive_number(snapshot.get('unidades_geradas'), 'Unidades registradas')
        if snapshot.get('material_resultante_id') != envase.material_resultante_id or not isclose(
                units * volume, envase.quantidade_litros, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError('Snapshot de produção não corresponde ao envase; confira o histórico.')
        return {'volume_por_unidade_litros': volume, 'unidades_envase': units, 'origem_unidades': 'registrado'}
    material = material_lookup.get_material(envase.material_resultante_id)
    if material is not None:
        from addons.addon_brewstation.features.feature_envase.services.envase_estoque_service import _volume_real_litros, VolumeRealNaoConfiguradoError
        try:
            volume = _volume_real_litros(material)
            units = positive_number(envase.quantidade_litros / volume, 'Unidades estimadas')
            return {'volume_por_unidade_litros': volume, 'unidades_envase': units, 'origem_unidades': 'estimado_cadastro_atual'}
        except (ValueError, VolumeRealNaoConfiguradoError):
            pass
    return {'volume_por_unidade_litros': None, 'unidades_envase': None, 'origem_unidades': 'indisponivel'}
