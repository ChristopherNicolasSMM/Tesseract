# 06 — Manutenção e Expansão (Feature Ingredientes)

## Adicionar um campo a `Malte`/`Lupulo`/`Levedura`

1. Editar `model/malte.py` (ou `lupulo.py`/`levedura.py`).
2. `python run.py generate --model addons/addon_brewstation/features/feature_ingredientes/model/malte.py --addon brewstation --feature ingredientes --overwrite`
3. Hooks (`*_hooks.py`) preservados automaticamente.

## Adicionar um novo tipo de ingrediente (ex.: Adjunto/Especiaria)

1. Criar `model/<novo>.py` seguindo o padrão dos três existentes —
   nome curto único no Addon (skill 02), `material_id` como referência
   fraca pro `Material` de `addon_estoque` (nunca FK direta, é
   cross-Addon).
2. `python run.py generate --model ... --addon brewstation --feature ingredientes`.
3. Atualizar `04-modelo-de-dados.md` desta Feature com a tabela nova.

## Resolver a pendência `Levedura` × `YeastStrain`

Hoje são conceitos desconectados por decisão (ver `01-visao-geral.md`).
Se um dia precisar ligar os dois (ex.: puxar atenuação/floculação da
especificação pra dentro do banco de cepas), a forma correta é
referência fraca por nome único (`display_field`, skill 11) — nunca FK
direta, porque `feature_yeast_bank` e `feature_ingredientes` são
Features irmãs (mesmo Addon, FK real seria até permitida pela skill
02, mas a referência fraca evita acoplar o schema de uma à outra
desnecessariamente).

## Pontos de extensão conhecidos

- Telas de cadastro/edição específicas (além do CRUD padrão gerado)
  ainda não foram desenhadas — pendência registrada em
  `01-visao-geral.md`.
- `IngredienteReceita` (linha de ingrediente de uma receita) mora em
  `feature_mash_control`, não aqui — qualquer expansão de "como um
  ingrediente entra numa receita" acontece lá, não nesta Feature.
