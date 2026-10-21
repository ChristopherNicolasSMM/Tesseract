"""Shared labels and categories; auxiliary heat never replaces the primary heater."""
ROLE_OPTIONS = [
    ('sensor_temp', 'Sensor de temperatura'),
    ('actor_heat', 'Atuador de aquecimento principal'),
    ('actor_heat_aux', 'Atuador de aquecimento auxiliar'),
    ('actor_flow', 'Atuador de fluxo'),
    *[(f'actor_pump_{i}', f'Bomba {i}') for i in range(1, 5)],
]
ROLE_CATEGORIES = {key: 'sensor' if key == 'sensor_temp' else 'actuator' for key, _ in ROLE_OPTIONS}
