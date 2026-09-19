"""
addons/addon_brewstation/features/feature_envase/services/unidade_conversao.py

Achado do Christopher (print de tela): a quantidade de um
RecipeIngredient vem na unidade da receita (ex.: lúpulo em gramas),
mas o preço (real, via Saldo.custo_medio, ou padrão, via
PrecoPadraoInsumo) é por unidade-base do Material (ex.: kg) — sem
converter, 22 g de lúpulo virava "22" direto na conta, multiplicando
por um preço por quilo (22 × R$120 = R$2640, em vez de
0.022 × R$120 = R$2,64).

Duas fontes de conversão, nessa ordem:
1. `MaterialUnidade` cadastrada para o Material (mais preciso — é o
   mecanismo que a skill 23 já criou pra isso). Só usada quando AMBAS
   as unidades (origem e destino) têm linha cadastrada pro mesmo
   Material.
2. Fallback genérico de massa/volume (g/kg/mg/ton, ml/l) — cobre o
   caso comum (like este) sem exigir cadastro prévio.

Se nenhuma das duas resolver (unidades de natureza diferente, ou
"un"/desconhecida), devolve a quantidade sem converter e
`conversao_confiavel=False` — nunca finge uma conversão que não pode
garantir, mas também não trava o cálculo.
"""
from __future__ import annotations

from core.db import db

_MASSA_PARA_GRAMA = {"mg": 0.001, "g": 1.0, "kg": 1000.0, "ton": 1_000_000.0, "t": 1_000_000.0}
_VOLUME_PARA_ML = {"ml": 1.0, "l": 1000.0, "lt": 1000.0}


def _fator_generico(unidade_origem: str, unidade_destino: str) -> float | None:
    uo, ud = unidade_origem.lower(), unidade_destino.lower()
    if uo in _MASSA_PARA_GRAMA and ud in _MASSA_PARA_GRAMA:
        return _MASSA_PARA_GRAMA[uo] / _MASSA_PARA_GRAMA[ud]
    if uo in _VOLUME_PARA_ML and ud in _VOLUME_PARA_ML:
        return _VOLUME_PARA_ML[uo] / _VOLUME_PARA_ML[ud]
    return None


def _fator_via_material_unidade(unidade_origem: str, unidade_destino: str, material_id: int) -> float | None:
    from addons.addon_estoque.root.model.material_unidade import MaterialUnidade

    row_o = (
        MaterialUnidade.query
        .filter(MaterialUnidade.material_id == material_id, MaterialUnidade.is_deleted.is_(False))
        .filter(db.func.lower(MaterialUnidade.unidade) == unidade_origem.lower())
        .first()
    )
    row_d = (
        MaterialUnidade.query
        .filter(MaterialUnidade.material_id == material_id, MaterialUnidade.is_deleted.is_(False))
        .filter(db.func.lower(MaterialUnidade.unidade) == unidade_destino.lower())
        .first()
    )
    if row_o and row_d and row_d.fator_para_base:
        return row_o.fator_para_base / row_d.fator_para_base
    return None


def converter_quantidade(
    quantidade: float,
    unidade_origem: str | None,
    unidade_destino: str | None,
    material_id: int | None = None,
) -> tuple[float, bool]:
    """
    Retorna (quantidade_convertida, conversao_confiavel).

    conversao_confiavel=False significa "não converti" (devolvi a
    quantidade como veio) porque não achei uma fonte de conversão —
    quem chama decide se avisa o usuário disso.
    """
    if not unidade_origem or not unidade_destino:
        return quantidade, True  # nada informado pra converter — mesmo comportamento de antes

    uo, ud = unidade_origem.strip(), unidade_destino.strip()
    if uo.lower() == ud.lower():
        return quantidade, True

    if material_id:
        fator = _fator_via_material_unidade(uo, ud, material_id)
        if fator is not None:
            return quantidade * fator, True

    fator = _fator_generico(uo, ud)
    if fator is not None:
        return quantidade * fator, True

    return quantidade, False
