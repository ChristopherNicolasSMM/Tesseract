"""Imagens raster incorporadas: sem URLs, caminhos ou arquivos persistentes."""
import base64
import binascii
from io import BytesIO
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 128 * 1024
MAX_TOTAL_IMAGE_BYTES = 512 * 1024
MAX_IMAGE_COUNT = 16
MAX_IMAGE_EDGE = 2048
MAX_IMAGE_PIXELS = 4_000_000
PREFIXES = {'data:image/png;base64,': ('PNG', 'image/png'),
            'data:image/jpeg;base64,': ('JPEG', 'image/jpeg')}


def decode_image(source):
    if type(source) is not str or len(source) > ((MAX_IMAGE_BYTES + 2) // 3) * 4 + 32:
        raise ValueError('Invalid image source')
    prefix = next((prefix for prefix in PREFIXES if source.startswith(prefix)), None)
    if prefix is None:
        raise ValueError('Only embedded PNG/JPEG images are supported')
    try:
        raw = base64.b64decode(source[len(prefix):], validate=True)
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise ValueError('Image exceeds byte limit')
        expected, mime = PREFIXES[prefix]
        with Image.open(BytesIO(raw), formats=['PNG', 'JPEG']) as image:
            width, height = image.size
            if image.format != expected or width < 1 or height < 1 or max(width, height) > MAX_IMAGE_EDGE or width * height > MAX_IMAGE_PIXELS or getattr(image, 'n_frames', 1) != 1:
                raise ValueError('Invalid image format or dimensions')
            image.verify()
        # verify() does not decode all pixel data; reopen and load to reject truncation.
        with Image.open(BytesIO(raw), formats=['PNG', 'JPEG']) as image:
            image.load()
        return raw, mime
    except (binascii.Error, OSError, UnidentifiedImageError, Image.DecompressionBombError, SyntaxError) as exc:
        raise ValueError('Invalid image data') from exc


def validate_image(props):
    if type(props) is not dict or set(props) - {'source', 'alt', 'width', 'height', 'style', 'pagination'}:
        raise ValueError('Invalid image properties')
    if type(props.get('alt', '')) is not str or len(props.get('alt', '')) > 240:
        raise ValueError('Invalid alternative text')
    for key, low, high in [('width', 5, 180), ('height', 5, 250)]:
        if key in props and (type(props[key]) is not int or not low <= props[key] <= high):
            raise ValueError('Invalid image dimensions')
    raw, _ = decode_image(props.get('source'))
    return len(raw)


def image_css(props):
    css = f'width:{props.get("width", 40)}mm;max-width:100%;'
    return css + (f'height:{props["height"]}mm;object-fit:contain;' if 'height' in props else 'height:auto;')
