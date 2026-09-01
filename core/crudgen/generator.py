"""
core/crudgen/generator.py

Orquestra a geração: lê metadados do model anotado (annotations.py),
resolve prefixo de tabela (manifest_utils.py), aplica o prefixo
(table_prefix.py), renderiza os templates e escreve os arquivos —
cada escrita passando por core/versioning.snapshot_if_needed().

Arquivos *_hooks.py e *_hooks.py.j2-derivados são escritos UMA ÚNICA
VEZ, nunca sobrescritos, mesmo com overwrite=True (skill 00/01).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from annotations import get_model_metadata
from core.crudgen.manifest_utils import resolve_table_prefix, resolve_output_dir
from core.crudgen.table_prefix import apply_table_prefix
from core.versioning import snapshot_if_needed, start_generation_run
from core.permissions_sync import sync_model_permissions

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), keep_trailing_newline=True)


def _to_snake_case(name: str) -> str:
    """
    PascalCase -> snake_case, conforme skill 01 (nome de arquivo é
    "[entidade_singular].py", ex.: YeastStrain -> yeast_strain).
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()

# (template, caminho relativo ao output_dir, é_hook)
_FILES_TO_GENERATE = [
    ("service.py.j2", "services/{snake_singular}_service.py", False),
    ("service_hooks.py.j2", "services/{snake_singular}_service_hooks.py", True),
    ("controller.py.j2", "controller/{plural}.py", False),
    ("controller_hooks.py.j2", "controller/{plural}_hooks.py", True),
    ("routes.py.j2", "api/routes/{plural}_routes.py", False),
    ("routes_hooks.py.j2", "api/routes/{plural}_routes_hooks.py", True),
    ("manage.html.j2", "templates/{plural}/manage.html", False),
    ("detail.html.j2", "templates/{plural}/detail.html", False),
    # Hook de TEMPLATE (skill 25) — primeiro do tipo no projeto: mesma
    # regra de qualquer *_hooks.py (criado uma única vez, nunca
    # sobrescrito, mesmo com overwrite=True), só que HTML em vez de
    # Python. Absorve botões/modais de ações em massa específicos de
    # uma entidade (ex.: os 4 de Materiais) sem risco de serem
    # perdidos no próximo --overwrite de manage.html.
    ("acoes_em_massa_extra_hook.html.j2", "templates/{plural}/_acoes_em_massa_extra.html", True),
]


def _module_path_for(project_root: Path, output_dir: Path) -> str:
    """Caminho de import Python (com pontos) equivalente a output_dir."""
    rel = output_dir.relative_to(project_root)
    return str(rel).replace("/", ".").replace("\\", ".")


def generate(
    model_class,
    *,
    project_root: Path,
    addon: str,
    feature: str | None = None,
    overwrite: bool = False,
    only: str | None = None,
    triggered_by: str = "cli:generate",
) -> dict:
    """
    Gera Service/Controller/Routes/Templates + hooks para um model já
    anotado, sincroniza as permissões (Camada 1 + Camada 2) e semeia
    FieldRule a partir de @required/@max_length/@min_length/@min_value
    (skill 12 — só na criação, nunca sobrescreve depois, mesmo
    espírito de hook: o admin passa a ser dono do registro na tela).

    `only`: restringe quais arquivos são (re)gerados. `None` (default)
    = todos os 8 artefatos, comportamento original. `"templates"` =
    só `manage.html`/`detail.html` — exige `overwrite=True` junto (não
    faz sentido pedir "só templates" sem também pedir pra sobrescrever
    o que já existe; levanta erro claro se vier sem isso).

    Retorna um resumo: {"written": [...], "skipped_existing": [...],
    "skipped_hooks": [...], "table_name": str, "permissions": {...},
    "field_rules_created": [...]}
    """
    if only is not None and only not in ("templates",):
        raise ValueError(f"'only' inválido: {only!r} — valores aceitos: 'templates'.")
    if only is not None and not overwrite:
        raise ValueError("--only exige --overwrite junto (senão os arquivos já existentes só seriam pulados, sem efeito nenhum).")
    meta = get_model_metadata(model_class)
    class_name = meta["name"]
    class_name_lower = _to_snake_case(class_name)  # ex.: YeastStrain -> yeast_strain
    plural = meta["plural"]
    label = meta["label"]

    full_prefix = resolve_table_prefix(project_root, addon, feature)
    table_name = apply_table_prefix(model_class, full_prefix)

    output_dir = resolve_output_dir(project_root, addon, feature)
    output_dir.mkdir(parents=True, exist_ok=True)

    snake_singular = _to_snake_case(class_name)
    model_module_path = _module_path_for(project_root, output_dir) + f".model.{snake_singular}"
    service_module_path = _module_path_for(project_root, output_dir) + f".services.{snake_singular}_service"
    hooks_module_path = _module_path_for(project_root, output_dir) + ".services"
    # Achado real (skill 21): controller_hooks (yeast_bank_events_hooks.py
    # etc.) mora em .controller, não em .services — hooks_module_path
    # acima serve só pro service.py.j2, não pode ser reaproveitado aqui.
    controller_hooks_module_path = _module_path_for(project_root, output_dir) + ".controller"
    output_module_path_label = str(output_dir.relative_to(project_root))

    web_prefix = f"/{addon.replace('_', '-')}/{plural.replace('_', '-')}"
    api_prefix = f"/api{web_prefix}"
    # Caminho RELATIVO (não a partir da raiz do projeto) — resolvido pelo
    # ChoiceLoader que o ModuleManager monta com o template_dir físico de
    # cada Feature/Addon como busca adicional (core/module_manager.py).
    # Usar o caminho completo aqui quebrava "extends core/base.html",
    # que só resolve se a raiz de busca for a mesma para os dois.
    template_dir = plural

    context = {
        "class_name": class_name,
        "class_name_lower": class_name_lower,
        "plural": plural,
        "label": label,
        "model_import_path": model_module_path,
        "service_import_path": service_module_path,
        "hooks_import_path": hooks_module_path,
        "controller_hooks_import_path": controller_hooks_module_path,
        "output_module_path": output_module_path_label,
        "web_prefix": web_prefix,
        "api_prefix": api_prefix,
        "template_dir": template_dir,
    }

    run_id = start_generation_run(class_name, triggered_by=triggered_by)

    files_to_generate = _FILES_TO_GENERATE
    if only == "templates":
        # Só os 2 artefatos HTML — hooks nunca entram nesse escopo por
        # definição (nenhum dos dois é hook). skill 12, item de fila.
        files_to_generate = [f for f in _FILES_TO_GENERATE if f[1].startswith("templates/")]

    written, skipped_existing, skipped_hooks = [], [], []

    for template_name, rel_path_pattern, is_hook in files_to_generate:
        rel_path = rel_path_pattern.format(plural=plural, snake_singular=_to_snake_case(class_name))
        dest_path = output_dir / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if is_hook and dest_path.exists():
            skipped_hooks.append(str(dest_path))
            continue

        if dest_path.exists() and not overwrite and not is_hook:
            skipped_existing.append(str(dest_path))
            continue

        if template_name.endswith(".html.j2"):
            raw = (_TEMPLATES_DIR / template_name).read_text(encoding="utf-8")
            content = (
                raw.replace("@@label@@", label)
                .replace("@@plural@@", plural)
                .replace("@@class_name_lower@@", class_name_lower)
            )
        else:
            template = _jinja_env.get_template(template_name)
            content = template.render(**context)

        dest_path.write_text(content, encoding="utf-8")
        snapshot_if_needed(str(dest_path), content)
        written.append(str(dest_path))

    perm_summary = sync_model_permissions(model_class, plural)

    field_rules_created: list[str] = []
    if only is None:
        # Seed de FieldRule só faz sentido numa geração completa — ver
        # docstring da função e da seção "field_rules_created" do
        # retorno. Fora do escopo de --only templates de propósito.
        field_rules_created = _seed_field_rules_from_validations(plural, meta.get("validations", {}))

    logger.info(
        "CrudGen: %s -> %d arquivo(s) escrito(s), %d existente(s) preservado(s), "
        "%d hook(s) preservado(s), %d FieldRule(s) semeada(s). Tabela: %s",
        class_name, len(written), len(skipped_existing), len(skipped_hooks),
        len(field_rules_created), table_name,
    )

    return {
        "written": written,
        "skipped_existing": skipped_existing,
        "skipped_hooks": skipped_hooks,
        "table_name": table_name,
        "permissions": perm_summary,
        "field_rules_created": field_rules_created,
        "generation_run_id": run_id,
    }


# rule_id do catálogo real (core/rules_catalog.py, grupo "Validação",
# já tem motor em static/js/rule_engine.js) — ligação feita nesta
# sessão (skill 12). Tipo de @required/@max_length/etc. (annotations/
# __init__.py, cls._validations) -> rule_id do catálogo.
_VALIDATION_TYPE_TO_RULE_ID = {
    "required": "obrigatorio",
    "max_length": "max_length",
    "min_length": "min_length",
    "min_value": "min_valor",
}


def _validation_params(rule_type: str, rule: dict) -> dict:
    if rule_type == "required":
        return {"message": rule.get("message")}
    if rule_type == "max_length":
        return {"max": rule.get("max"), "message": rule.get("message")}
    if rule_type == "min_length":
        return {"min": rule.get("min"), "message": rule.get("message")}
    if rule_type == "min_value":
        return {"min": rule.get("min"), "message": rule.get("message")}
    return {}


def _seed_field_rules_from_validations(plural: str, validations: dict) -> list[str]:
    """
    Cria FieldRule (model/core/field_rule.py) a partir de
    @required/@max_length/@min_length/@min_value do model — SÓ na
    criação, nunca atualiza um registro já existente (mesmo espírito
    de hook: uma vez semeado, o admin é dono via tela de Field Rules,
    regenerar não pisa em cima de uma customização manual).
    """
    from model.core.field_rule import FieldRule
    from core.db import db

    created: list[str] = []
    for field, rules in validations.items():
        for order, rule in enumerate(rules):
            rule_id = _VALIDATION_TYPE_TO_RULE_ID.get(rule.get("type"))
            if not rule_id:
                continue
            ja_existe = FieldRule.query.filter_by(
                entity_key=plural, field_name=field, rule_id=rule_id,
            ).first()
            if ja_existe:
                continue
            db.session.add(FieldRule(
                entity_key=plural, field_name=field, rule_id=rule_id,
                params_json=_validation_params(rule["type"], rule), order=order,
            ))
            created.append(f"{plural}.{field}:{rule_id}")

    if created:
        db.session.commit()
    return created
