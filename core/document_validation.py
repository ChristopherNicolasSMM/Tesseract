"""Documentos brasileiros: formato estrito e DV, sem consulta cadastral."""
import re
from core.validators import validate_cpf


class DocumentValidator:
    @staticmethod
    def cpf(value):
        if not isinstance(value, str) or not re.fullmatch(r'(?:[0-9]{11}|[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2})', value.strip()):
            raise ValueError('CPF inválido.')
        value = re.sub(r'[.-]', '', value.strip())
        if not validate_cpf(value):
            raise ValueError('CPF inválido.')
        return value

    @staticmethod
    def cnpj(value):
        if not isinstance(value, str) or not value.isascii():
            raise ValueError('CNPJ inválido.')
        value = value.strip().upper()
        if not re.fullmatch(r'(?:[A-Z0-9]{12}[0-9]{2}|[A-Z0-9]{2}\.[A-Z0-9]{3}\.[A-Z0-9]{3}/[A-Z0-9]{4}-[0-9]{2})', value):
            raise ValueError('CNPJ inválido.')
        value = re.sub(r'[./-]', '', value)
        if value == value[0] * 14:
            raise ValueError('CNPJ inválido.')
        def digit(part):
            total = sum((ord(char) - 48) * (2 + index % 8) for index, char in enumerate(reversed(part)))
            remainder = total % 11
            return str(0 if remainder < 2 else 11 - remainder)
        first = digit(value[:12])
        if value[12:] != first + digit(value[:12] + first):
            raise ValueError('CNPJ inválido.')
        return value

    @staticmethod
    def cep(value):
        if not isinstance(value, str) or not re.fullmatch(r'[0-9]{5}-?[0-9]{3}', value.strip()):
            raise ValueError('CEP deve conter oito dígitos.')
        return value.strip().replace('-', '')

    @staticmethod
    def email(value):
        if not isinstance(value, str) or len(value.strip()) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value.strip()):
            raise ValueError('E-mail inválido.')
        return value.strip()

    @staticmethod
    def phone(value):
        if not isinstance(value, str) or not re.fullmatch(r'\+?[0-9() .-]+', value.strip()):
            raise ValueError('Telefone inválido.')
        digits = re.sub(r'[^0-9]', '', value)
        if not 8 <= len(digits) <= 15:
            raise ValueError('Telefone deve conter de oito a quinze dígitos.')
        return ('+' if value.strip().startswith('+') else '') + digits
