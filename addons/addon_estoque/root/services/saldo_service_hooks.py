"""
addons/addon_estoque/root/services/saldo_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos

CUSTOMIZAÇÃO (achado do Christopher): `valor_total_estoque`/
`estoque_minimo` nulos mostravam em branco na tela — decisão de
sessão: tratar como 0 em vez de deixar nulo, resolvido aqui (na
gravação), não espalhado em cada template que exibe Saldo.
"""


def pai_apply_fields(obj, data):
    if obj.valor_total_estoque is None:
        obj.valor_total_estoque = 0.0
    if obj.estoque_minimo is None:
        obj.estoque_minimo = 0.0
