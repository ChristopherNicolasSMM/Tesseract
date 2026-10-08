"""Propriedades tipadas; nunca aceitar CSS arbitrário de templates."""
ALIGNMENTS = ('left', 'center', 'right', 'justify')
RANGES = {'font_size': (8, 48), 'margin_top': (0, 48), 'margin_bottom': (0, 48), 'padding': (0, 24)}


def validate_style(value, *, table=False):
    if type(value) is not dict or set(value) - (set(RANGES) | {'align', 'bold'} | ({'cell_padding'} if table else set())):
        return False
    for key, item in value.items():
        if key == 'align':
            if type(item) is not str or item not in ALIGNMENTS:
                return False
        elif key == 'bold':
            if type(item) is not bool:
                return False
        else:
            low, high = (0, 24) if key == 'cell_padding' else RANGES[key]
            if type(item) is not int or not low <= item <= high:
                return False
    return True


def style_css(value):
    names = {'align':'text-align', 'font_size':'font-size', 'margin_top':'margin-top',
             'margin_bottom':'margin-bottom', 'padding':'padding', 'cell_padding':'--report-cell-padding'}
    return ';'.join(('font-weight:' + ('700' if item else '400')) if key == 'bold'
                    else names[key] + ':' + (item if key == 'align' else str(item)+'pt')
                    for key, item in sorted(value.items()))
