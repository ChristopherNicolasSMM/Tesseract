"""
core/validators.py

Validadores reaproveitáveis de formato/documento, portados do PyTeca.
Função pura — quem usa decide o que fazer com ValueError/False
(camada de serviço/API converte em 422, nunca deixa propagar como 500).
"""
from __future__ import annotations

import re


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def validate_cpf(cpf: str) -> bool:
    """
    Valida CPF pelo algoritmo oficial dos dois dígitos verificadores.
    Aceita com ou sem máscara. Rejeita sequências repetidas
    (111.111.111-11 etc.) — matematicamente "válidas" pelo algoritmo,
    mas sempre fraudulentas.
    """
    digits = only_digits(cpf)

    if len(digits) != 11:
        return False
    if digits == digits[0] * 11:
        return False

    def _check_digit(slice_digits: str, weight_start: int) -> int:
        total = sum(
            int(d) * w for d, w in zip(slice_digits, range(weight_start, 1, -1))
        )
        remainder = (total * 10) % 11
        return 0 if remainder == 10 else remainder

    first_check = _check_digit(digits[:9], 10)
    if first_check != int(digits[9]):
        return False

    second_check = _check_digit(digits[:10], 11)
    return second_check == int(digits[10])


def format_cpf(cpf: str) -> str:
    digits = only_digits(cpf)
    if len(digits) != 11:
        return cpf
    return f"{digits[0:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"


def validate_cep(cep: str) -> bool:
    return len(only_digits(cep)) == 8


def format_cep(cep: str) -> str:
    digits = only_digits(cep)
    if len(digits) != 8:
        return cep
    return f"{digits[0:5]}-{digits[5:8]}"
