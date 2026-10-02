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
