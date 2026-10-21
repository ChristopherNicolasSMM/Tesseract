"""Fixed persisted values; translated labels never become database identifiers."""
CATEGORY_OPTIONS = [('sensor', 'Sensor'), ('actuator', 'Atuador'), ('hybrid', 'Híbrido')]
DATA_TYPE_OPTIONS = [('float', 'Número decimal'), ('int', 'Número inteiro'),
                     ('bool', 'Liga/desliga'), ('string', 'Texto')]


def canonical_category(value):
    key = value.strip().casefold() if isinstance(value, str) else value
    return {'atuador': 'actuator', 'actuador': 'actuator', 'actuator': 'actuator',
            'sensor': 'sensor', 'híbrido': 'hybrid', 'hibrido': 'hybrid', 'hybrid': 'hybrid'}.get(key, key)
