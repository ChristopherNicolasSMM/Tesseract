"""
core/formatting.py

Formatação de moeda/data — lida de `system_config` (skill 03, seção
5), "pra servir em todo o sistema" (achado do Christopher, sessão
addon_estoque: telas de Saldo/Movimentação mostravam número cru e
data em ISO). Nunca hardcoda "R$"/"dd/mm/yyyy" direto num template —
sempre passa por aqui, pra trocar em UM lugar só quando o padrão do
sistema mudar (ex.: internacionalização futura, moeda diferente).

Chaves em `system_config` (todas opcionais — sem elas, usa os
`_PADRAO_*` abaixo, nunca quebra por falta de configuração):

| Chave | Tipo | Padrão | Uso |
|---|---|---|---|
| `format.moeda_simbolo` | string | `"R$"` | Prefixo de `formatar_moeda()` |
| `format.moeda_casas_decimais` | int | `2` | Casas decimais de `formatar_moeda()` |
| `format.data_formato` | string | `"%d/%m/%Y"` | strftime de `formatar_data()` |
"""
from datetime import date, datetime

CHAVE_MOEDA_SIMBOLO = "format.moeda_simbolo"
CHAVE_MOEDA_CASAS_DECIMAIS = "format.moeda_casas_decimais"
CHAVE_DATA_FORMATO = "format.data_formato"

PADRAO_MOEDA_SIMBOLO = "R$"
PADRAO_MOEDA_CASAS_DECIMAIS = 2
PADRAO_DATA_FORMATO = "%d/%m/%Y"


def _numero_estilo_br(valor: float, casas: int) -> str:
    """1234.5 -> "1.234,50" (separador de milhar '.', decimal ',') —
    sem depender do módulo `locale` do SO (frágil, varia por
    ambiente/instalação — evitado de propósito)."""
    texto = f"{valor:,.{casas}f}"  # formato EN: "1,234.50"
    parte_inteira, _, parte_decimal = texto.partition(".")
    parte_inteira = parte_inteira.replace(",", ".")
    return f"{parte_inteira},{parte_decimal}" if parte_decimal else parte_inteira


def formatar_moeda(valor) -> str:
    """`None` vira "—" (nunca "R$ None"). Lê símbolo/casas decimais de
    `system_config` a cada chamada — customização de sessão (skill 03)
    é lida em runtime, nunca cacheada em import time."""
    if valor is None:
        return "—"
    from model.core.system_config import SystemConfig

    simbolo = SystemConfig.get(CHAVE_MOEDA_SIMBOLO, PADRAO_MOEDA_SIMBOLO)
    casas = SystemConfig.get(CHAVE_MOEDA_CASAS_DECIMAIS, PADRAO_MOEDA_CASAS_DECIMAIS)
    try:
        casas = int(casas)
    except (TypeError, ValueError):
        casas = PADRAO_MOEDA_CASAS_DECIMAIS
    try:
        valor_float = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    return f"{simbolo} {_numero_estilo_br(valor_float, casas)}"


def formatar_data(valor) -> str:
    """Aceita `date`/`datetime`/string ISO (`YYYY-MM-DD...`). `None`
    vira "—". Formato lido de `system_config` a cada chamada, mesmo
    raciocínio de `formatar_moeda()`."""
    if valor is None:
        return "—"
    from model.core.system_config import SystemConfig

    formato = SystemConfig.get(CHAVE_DATA_FORMATO, PADRAO_DATA_FORMATO)

    if isinstance(valor, str):
        try:
            valor = date.fromisoformat(valor[:10])
        except ValueError:
            return valor
    if isinstance(valor, datetime):
        valor = valor.date()
    if not isinstance(valor, date):
        return str(valor)

    try:
        return valor.strftime(formato)
    except (ValueError, TypeError):
        return valor.strftime(PADRAO_DATA_FORMATO)


def registrar_filtros_jinja(app) -> None:
    """Registra `{{ valor | moeda }}` e `{{ valor | data_br }}`
    globalmente — disponíveis em qualquer template do sistema, não só
    addon_estoque (chamado uma vez em core/app_factory.py)."""
    app.jinja_env.filters["moeda"] = formatar_moeda
    app.jinja_env.filters["data_br"] = formatar_data
