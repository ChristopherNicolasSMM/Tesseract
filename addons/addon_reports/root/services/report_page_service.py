"""Página e fragmentação tipadas, sem CSS arbitrário fornecido pelo cliente."""
PAGE_SIZES = {'A4': (210, 297), 'A5': (148, 210), 'Letter': (215.9, 279.4)}
MARGIN_KEYS = ('margin_top', 'margin_right', 'margin_bottom', 'margin_left')
DEFAULT_PAGE = {'format':'A4', 'orientation':'portrait', 'number_pages':False, **{key:15 for key in MARGIN_KEYS}}


def page_config(value=None):
    if value is None:
        return dict(DEFAULT_PAGE)
    if type(value) is not dict or set(value) - set(DEFAULT_PAGE):
        raise ValueError('Invalid page settings')
    result = {**DEFAULT_PAGE, **value}
    if type(result['format']) is not str or result['format'] not in PAGE_SIZES or result['orientation'] not in ('portrait', 'landscape'):
        raise ValueError('Invalid paper format or orientation')
    if type(result['number_pages']) is not bool:
        raise ValueError('Invalid page numbering')
    for key in MARGIN_KEYS:
        if type(result[key]) is not int or not 0 <= result[key] <= 40:
            raise ValueError('Invalid page margin')
    if result['number_pages'] and result['margin_bottom'] < 8:
        raise ValueError('Page numbering requires a bottom margin of 8 mm')
    return result


def page_dimensions(config):
    width, height = PAGE_SIZES[config['format']]
    return (height, width) if config['orientation']=='landscape' else (width, height)


def page_css(config):
    size = config['format'] + (' landscape' if config['orientation']=='landscape' else '')
    margins = [config[key] for key in MARGIN_KEYS]
    margin_css = ' '.join(str(value)+'mm' for value in margins)
    if len(set(margins))==1:
        margin_css = str(margins[0])+'mm'
    width, height = page_dimensions(config)
    footer = ' @bottom-right { content: "Página " counter(page) " de " counter(pages); font:8pt sans-serif; color:#182230; }' if config['number_pages'] else ''
    return f'@page {{ size: {size}; margin: {margin_css};{footer} }}', f'max-width:{width:g}mm; min-height:{height:g}mm; padding:{margin_css};'


def validate_pagination(value):
    return type(value) is dict and not set(value) - {'break_before','break_after','keep_together'} and all(type(item) is bool for item in value.values())


def pagination_css(value):
    return ';'.join(css for key,css in [('break_before','break-before:page'),('break_after','break-after:page'),('keep_together','break-inside:avoid')] if value.get(key))
