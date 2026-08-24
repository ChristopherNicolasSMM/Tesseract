"""
addons/addon_brewstation/features/feature_yeast_bank/controller/yeast_starter_logs_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito.

`block_create` (skill 21): decisão do Christopher, opção A — criação
de Starter só é permitida a partir de um Evento do Banco (tipo
"Starter"), nunca direto por esta tela. Edição/consulta de Starters
já existentes continua funcionando normal — só a criação direta é
bloqueada.
"""


def block_create(data):
    return (
        "Novos Starters só podem ser criados a partir de um Evento do "
        "Banco (tipo \"Starter\") — acesse Eventos do Banco e crie um "
        "evento desse tipo."
    )
