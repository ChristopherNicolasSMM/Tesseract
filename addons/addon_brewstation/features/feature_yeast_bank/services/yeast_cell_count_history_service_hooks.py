"""
addons/addon_brewstation/features/feature_yeast_bank/services/yeast_cell_count_history_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos

`pai_apply_fields` (skill 22, 2026-08-24): calcula
cells_per_ml/viability_percent/viable_cells_per_ml automaticamente a
partir dos campos brutos de entrada da câmara de Neubauer
(cells_counted_live/_dead, squares_counted, dilution_factor), quando
esses campos brutos vêm preenchidos e os de resultado ainda estão
vazios — nunca sobrescreve valor já informado manualmente.

Fórmula (câmara de Neubauer — prática padrão de contagem de levedura,
skill 22): células/mL = (vivas + mortas) × (25 / quadrados_contados) ×
fator_de_diluição × 10.000; viabilidade% = vivas × 100 / (vivas + mortas).
"""


def _calcular_neubauer(obj) -> None:
    if obj.cells_counted_live is None or obj.cells_counted_dead is None:
        return  # sem os dois brutos, não dá pra calcular nada

    total = obj.cells_counted_live + obj.cells_counted_dead
    if total <= 0:
        return  # divisão por zero — nenhuma célula contada, viva ou morta

    quadrados = obj.squares_counted or 5
    diluicao = obj.dilution_factor if obj.dilution_factor is not None else 1.0

    cells_per_ml = total * (25 / quadrados) * diluicao * 10_000
    viability_percent = (obj.cells_counted_live * 100) / total
    viable_cells_per_ml = cells_per_ml * viability_percent / 100

    if obj.cells_per_ml is None:
        obj.cells_per_ml = round(cells_per_ml, 2)
    if obj.viability_percent is None:
        obj.viability_percent = round(viability_percent, 2)
    if obj.viable_cells_per_ml is None:
        obj.viable_cells_per_ml = round(viable_cells_per_ml, 2)


def pai_apply_fields(obj, data):
    _calcular_neubauer(obj)
