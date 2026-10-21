"""
addons/addon_brewstation/features/feature_mash_control/controller/brew_plant_mappings_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.
"""


def block_create(data):
    """Match workspace safeguards without replacing generated CRUD controllers."""
    from ..model.brew_plant_mapping import BrewPlantMapping
    from ..model.brew_plant_vessel import BrewPlantVessel
    from ..model.mapping_roles import ROLE_CATEGORIES
    from addons.addon_device_manager.root.services.device_function_lookup import get_function_by_name
    try:
        vessel_id = int(data.get('vessel_id'))
    except (ValueError, TypeError):
        return 'Selecione um tanque existente.'
    if not BrewPlantVessel.query.filter_by(id=vessel_id, is_deleted=False).first():
        return 'Selecione um tanque existente.'
    role = str(data.get('role_key') or '').strip()
    function = get_function_by_name(data.get('device_function_name'))
    if not function:
        return 'Busque e selecione uma função de dispositivo existente na lista.'
    expected = ROLE_CATEGORIES.get(role)
    if expected and function.get('category') not in (expected, 'hybrid'):
        return f"Papel incompatível: a função deve ter categoria '{expected}' ou 'hybrid' no Device Manager."
    if BrewPlantMapping.query.filter_by(vessel_id=vessel_id, role_key=role, is_deleted=False).first():
        return 'Este tanque já possui esse papel. Para outra fonte, selecione aquecimento auxiliar.'
    return None
