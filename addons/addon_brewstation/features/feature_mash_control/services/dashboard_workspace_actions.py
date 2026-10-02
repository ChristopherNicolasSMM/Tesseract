"""Configuração manual de fundo/padrão; sem editar widgets ou runtime."""
import re
from urllib.parse import urlsplit

from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout


def background_color(value):
    value = (value or '').strip()
    if not re.fullmatch(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?(?:[0-9a-fA-F]{2})?', value) or len(value) not in (4, 7, 9):
        raise ValueError('Informe cor hexadecimal: #RGB, #RRGGBB ou #RRGGBBAA.')
    return value


def background_image(value):
    value = (value or '').strip()
    if not value:
        return None
    if len(value) > 500 or re.search(r'[\s\x00-\x1f\x7f\\]', value):
        raise ValueError('URL da imagem inválida ou maior que 500 caracteres.')
    try:
        parsed = urlsplit(value)
        relative = value.startswith('/') and not value.startswith('//') and not parsed.netloc and not parsed.scheme
        remote = parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username and not parsed.password
        if not (relative or remote):
            raise ValueError
    except ValueError:
        raise ValueError('Use URL HTTP/HTTPS ou caminho local iniciado por / para a imagem.') from None
    return value


def render_background(layout):
    """Legados inválidos não entram no style/src; leitura não corrige cadastro."""
    try:
        color = background_color(layout.background_color)
    except ValueError:
        color = '#0f1117'
    try:
        image = background_image(layout.background_image_url)
    except ValueError:
        image = None
    return {'dashboard_background_color': color, 'dashboard_background_image_url': image}


def configure_layout(plant_id, layout_id, *, color, image, is_default):
    layout = (DashboardLayout.query.join(BrewPlant)
              .filter(DashboardLayout.id == layout_id, DashboardLayout.plant_id == plant_id,
                      DashboardLayout.is_deleted.is_(False), BrewPlant.is_deleted.is_(False)).first())
    if layout is None:
        raise LookupError('Painel desta planta não encontrado.')
    color = background_color(color)
    image = background_image(image)
    try:
        if is_default:
            # Primeiro write serializa concorrência SQLite; sem commit intermediário.
            DashboardLayout.query.filter(DashboardLayout.plant_id == plant_id,
                DashboardLayout.id != layout_id, DashboardLayout.is_deleted.is_(False)).update(
                    {'is_default': False}, synchronize_session='fetch')
        layout.background_color = color
        layout.background_image_url = image
        layout.is_default = is_default
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return layout


def maintain_layout(plant_id, layout_id, action):
    """Reaproveita trash/restore existentes, com escopo e rollback locais."""
    from addons.addon_brewstation.features.feature_mash_control.services.dashboard_layout_service import DashboardLayoutService
    layout = (DashboardLayout.query.join(BrewPlant)
              .filter(DashboardLayout.id == layout_id, DashboardLayout.plant_id == plant_id,
                      BrewPlant.is_deleted.is_(False)).first())
    if layout is None:
        raise LookupError('Painel desta planta não encontrado.')
    if action not in ('trash', 'restore'):
        raise ValueError('Ação de manutenção inválida.')
    if action == 'trash' and layout.is_deleted:
        raise ValueError('O painel já está na lixeira.')
    if action == 'restore' and not layout.is_deleted:
        raise ValueError('O painel não está na lixeira.')
    try:
        if action == 'restore':
            # Primeiro write serializa restauração/configuração no SQLite.
            # A decisão de preservar o padrão é feita no próprio UPDATE.
            active_default = DashboardLayout.query.filter_by(
                plant_id=plant_id, is_deleted=False, is_default=True).correlate(None).exists()
            DashboardLayout.query.filter_by(id=layout_id, plant_id=plant_id,
                is_deleted=True, is_default=True).filter(active_default).update(
                    {'is_default': False}, synchronize_session=False)
            db.session.refresh(layout)
            if not layout.is_deleted:
                raise ValueError('O painel não está na lixeira.')
        service = DashboardLayoutService()
        result = getattr(service, action)(layout_id)
        if not result.success:
            raise ValueError(result.error)
    except Exception:
        db.session.rollback()
        raise
    if action == 'restore':
        return layout
    remaining = DashboardLayout.query.filter_by(plant_id=plant_id, is_deleted=False)
    return (remaining.filter_by(is_default=True).order_by(DashboardLayout.id).first()
            or remaining.order_by(DashboardLayout.id).first())
