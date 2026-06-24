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
    ("form_modal.html.j2", "templates/{plural}/_modals/form_modal.html", False),
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
    triggered_by: str = "cli:generate",
) -> dict:
    """
    Gera Service/Controller/Routes/Templates + hooks para um model já
    anotado, e sincroniza as permissões (Camada 1 + Camada 2).

    Retorna um resumo: {"written": [...], "skipped_existing": [...],
    "skipped_hooks": [...], "table_name": str, "permissions": {...}}
    """
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
        "output_module_path": output_module_path_label,
        "web_prefix": web_prefix,
        "api_prefix": api_prefix,
        "template_dir": template_dir,
    }

    run_id = start_generation_run(class_name, triggered_by=triggered_by)

    written, skipped_existing, skipped_hooks = [], [], []

    for template_name, rel_path_pattern, is_hook in _FILES_TO_GENERATE:
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

    logger.info(
        "CrudGen: %s -> %d arquivo(s) escrito(s), %d existente(s) preservado(s), "
        "%d hook(s) preservado(s). Tabela: %s",
        class_name, len(written), len(skipped_existing), len(skipped_hooks), table_name,
    )

    return {
        "written": written,
        "skipped_existing": skipped_existing,
        "skipped_hooks": skipped_hooks,
        "table_name": table_name,
        "permissions": perm_summary,
        "generation_run_id": run_id,
    }
