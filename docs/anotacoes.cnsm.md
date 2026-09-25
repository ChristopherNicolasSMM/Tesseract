git am --abort                              # ou se já fez abort:
Remove-Item -Recurse -Force .git\rebase-apply
git restore <arquivo_conflitante>           # restaura ao HEAD
git am <patch>                              # tenta de novo


# Aplicar ignorando espaço ou quebra de linha
git apply --ignore-space-change --whitespace=fix 0001-*.patch
# Uso padrão
git am --keep-cr 

---

# Exemplos

### Exemplo CRUDGen

python run.py generate --model ./addons/addon_brewstation/features/feature_yeast_bank/model/yeast_strain.py --addon brewstation --feature yeast_bank --overwrite


### Exemplos para preenchimento chave em model
'''Python 

@enum_field("step_type", options=["mash", "boil", "alert"])
@enum_field("status", options=["draft", "active", "paused", "completed", "aborted"])

@choices("status", label="Status")
@choices("origem_receita", label="Origem")
@choices("step_type", label="Tipo de Etapa")
@choices("tipo", label="Subtipo (mostura)")
@choices("source", label="Origem")


"""
        @weak_ref("material_id",
                   resolver="addons.addon_estoque.root.services.material_lookup.get_material",
                   options="materials")
        class Malte(db.Model):
            material_id = db.Column(db.Integer, nullable=False, index=True)  # SEM FK

    Múltiplas @weak_ref podem ser empilhadas se o model tiver mais de
    um campo de referência fraca.
    """




@field_labels({
    "material_id": "Material",
    "fornecedor_id": "Fornecedor",
    # ...outros campos que quiser renomear
})

'''

---


