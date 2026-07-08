"""
tests/test_crudgen_cli_generate_relationship_bug.py

Regressão do bug encontrado na skill 11 (docs/skills/11-referencia-fraca-e-display-field.md,
seção 10 — ver também BACKLOG.md): `flask generate --model ... --overwrite`
falhava com NoForeignKeysError ao regenerar um model com relationship()
real pra outra tabela do mesmo Addon/Feature já prefixada, porque
`generate_cmd` recarregava o arquivo isolado via
`importlib.util.spec_from_file_location` em vez de reaproveitar a
classe já importada normalmente no boot (`register_models()`).

Os testes de `test_phase4_crudgen.py` cobrem `generate()` (a função
core) chamando-a diretamente com a classe já em memória — nunca
passam pelo carregamento via CLI (`generate_cmd`), que é exatamente
onde o bug vivia. Este arquivo cobre a lacuna: invoca o comando real
via `app.test_cli_runner()`, igual a `python run.py generate ...`.
"""
from core.app_factory import create_app


def test_generate_cli_regenera_model_com_relationship_real_sem_erro(tmp_path):
    """
    ItemEnvase.envase é relationship() real pra Envase (mesmo Addon,
    skill 02 permite FK dentro do mesmo Addon). Regenerar via CLI não
    pode quebrar com NoForeignKeysError — bug real corrigido nesta
    sessão (core/cli.py, generate_cmd agora reimporta pelo dotted path
    real do pacote, reaproveitando a classe já mapeada no boot).
    """
    app = create_app(env="testing")
    runner = app.test_cli_runner()

    result = runner.invoke(args=[
        "generate",
        "--model", "addons/addon_brewstation/features/feature_envase/model/item_envase.py",
        "--addon", "brewstation",
        "--feature", "envase",
        "--overwrite",
    ])

    assert result.exit_code == 0, result.output
    assert "NoForeignKeysError" not in result.output
    assert "Tabela:" in result.output


def test_generate_cli_regenera_recipe_ingredient_sem_erro():
    """Mesmo cenário, segunda entidade afetada pelo bug original (RecipeIngredient.recipe)."""
    app = create_app(env="testing")
    runner = app.test_cli_runner()

    result = runner.invoke(args=[
        "generate",
        "--model", "addons/addon_brewstation/features/feature_mash_control/model/recipe_ingredient.py",
        "--addon", "brewstation",
        "--feature", "mash_control",
        "--overwrite",
    ])

    assert result.exit_code == 0, result.output
    assert "NoForeignKeysError" not in result.output


def test_generate_cli_regenera_model_sem_relationship_continua_funcionando():
    """Entidade sem relationship() real (só @weak_ref) - já funcionava
    antes da correção, continua funcionando depois (não regrediu)."""
    app = create_app(env="testing")
    runner = app.test_cli_runner()

    result = runner.invoke(args=[
        "generate",
        "--model", "addons/addon_brewstation/features/feature_ingredientes/model/malte.py",
        "--addon", "brewstation",
        "--feature", "ingredientes",
        "--overwrite",
    ])

    assert result.exit_code == 0, result.output


def test_generate_cli_only_templates_via_flag_real():
    """
    Skill 12 — --only templates via CLI real (não só a função generate()
    direto). Regenera Malte só nos templates, exige --overwrite junto.
    """
    app = create_app(env="testing")
    runner = app.test_cli_runner()

    result = runner.invoke(args=[
        "generate",
        "--model", "addons/addon_brewstation/features/feature_ingredientes/model/malte.py",
        "--addon", "brewstation",
        "--feature", "ingredientes",
        "--overwrite",
        "--only", "templates",
    ])

    assert result.exit_code == 0, result.output
    assert "Arquivos escritos: 2" in result.output


def test_generate_cli_only_sem_overwrite_mostra_erro_amigavel():
    app = create_app(env="testing")
    runner = app.test_cli_runner()

    result = runner.invoke(args=[
        "generate",
        "--model", "addons/addon_brewstation/features/feature_ingredientes/model/malte.py",
        "--addon", "brewstation",
        "--feature", "ingredientes",
        "--only", "templates",
    ])

    assert result.exit_code == 0  # comando não crasha, só mostra a mensagem
    assert "Erro:" in result.output
    assert "overwrite" in result.output
