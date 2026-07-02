"""
core/module_discovery.py

Auto-descoberta de rotas/models via pkgutil (skill 09), escopada por
módulo (Addon/Feature/Plugin) — adaptação do mecanismo real do PyTeca
(`main.py::discover_and_register_blueprints` +
`utils/generate_model/menu_builder.py::get_items_from_models`) à
arquitetura tri-nível do Tesseract, que precisa saber de qual módulo
veio cada coisa antes de aplicar prefixo de tabela (skill 02) — por
isso a descoberta aqui é sempre escopada a UM pacote específico, nunca
uma varredura global como no PyTeca (que é monolítico).

Usado por core/module_base.py, core/addon_base.py e
core/feature_base.py como implementação DEFAULT de
register_routes()/register_models()/get_transactions() — qualquer
Addon/Feature/Plugin que sobrescrever esses métodos manualmente
continua funcionando exatamente igual (override sempre vence, ver
skill 09 §0).
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def own_module_dir(obj: Any) -> Path | None:
    """
    Pasta em disco onde `obj` (instância de Addon/Feature/Plugin) foi
    definida — SEM descer para root/ (isso é feito por
    `own_base_package`, que é o que model/controller/rotas usam;
    `get_features()`, seção mais abaixo, precisa da pasta "crua",
    porque features/ é irmã de root/, nunca filha dela).
    """
    module_name = type(obj).__module__
    mod = sys.modules.get(module_name)
    if not mod or not getattr(mod, "__file__", None):
        logger.debug(
            "own_module_dir: não foi possível resolver __file__ de %s "
            "(module_name=%s) — auto-descoberta não vai encontrar nada "
            "para esta instância.", obj, module_name,
        )
        return None
    return Path(mod.__file__).resolve().parent


def dotted_from_path(path: Path) -> str | None:
    """Converte um caminho absoluto dentro do projeto em pacote pontuado."""
    try:
        rel = path.relative_to(_PROJECT_ROOT)
    except ValueError:
        logger.warning(
            "dotted_from_path: %s está fora de %s — auto-descoberta pulada.",
            path, _PROJECT_ROOT,
        )
        return None
    return ".".join(rel.parts)


def own_base_package(obj: Any) -> tuple[str, Path] | None:
    """
    Pacote-base (dotted) e pasta em disco de onde `obj` (instância de
    Addon/Feature/Plugin) deve procurar model/controller/api/routes
    para a auto-descoberta.

    Addon com pasta root/ (ex.: addon_device_manager, skill 01) usa
    root/ como base; Feature/Plugin (sem root/) e Addon sem núcleo
    próprio (ex.: addon_brewstation, cujo conteúdo real mora todo em
    Features) usam a própria pasta do módulo — que nesse último caso
    simplesmente não tem model/controller/api, então a descoberta
    retorna listas vazias, igual o `return []` manual que já existia.
    """
    module_dir = own_module_dir(obj)
    if module_dir is None:
        return None

    base_dir = module_dir / "root" if (module_dir / "root").is_dir() else module_dir
    dotted = dotted_from_path(base_dir)
    if dotted is None:
        return None
    return dotted, base_dir


def _walk_package_modules(dotted_package: str) -> list:
    """
    Importa `dotted_package` e todo submódulo dele (pkgutil.walk_packages,
    mesmo mecanismo do PyTeca). Pacote inexistente (ex.: módulo sem
    pasta model/ própria) não é erro — só não descobre nada.
    """
    try:
        package = importlib.import_module(dotted_package)
    except ModuleNotFoundError:
        return []
    except Exception:
        logger.exception(
            "Falha ao importar %s durante auto-descoberta (skill 09) — "
            "pulando este pacote.", dotted_package,
        )
        return []

    modules = [package]
    if hasattr(package, "__path__"):
        for _, modname, _ in pkgutil.walk_packages(package.__path__, prefix=dotted_package + "."):
            try:
                modules.append(importlib.import_module(modname))
            except Exception:
                logger.exception(
                    "Falha ao importar %s durante auto-descoberta (skill 09) "
                    "— pulando este módulo, o resto da descoberta continua.",
                    modname,
                )
    return modules


def discover_models(base_package: str) -> list[type]:
    """
    Toda classe db.Model DEFINIDA (não apenas importada) em
    `{base_package}.model` e seus submódulos. Equivale ao que
    `register_models()` retornava manualmente até a skill 09.
    """
    from core.db import db

    models: list[type] = []
    seen_ids: set[int] = set()
    for module in _walk_package_modules(f"{base_package}.model"):
        for attr_name in dir(module):
            attr = getattr(module, attr_name, None)
            if (
                isinstance(attr, type)
                and issubclass(attr, db.Model)
                and attr is not db.Model
                and getattr(attr, "__module__", None) == module.__name__
                and id(attr) not in seen_ids
            ):
                seen_ids.add(id(attr))
                models.append(attr)
    return models


def discover_blueprints(base_package: str) -> list:
    """
    Toda instância de flask.Blueprint encontrada em
    `{base_package}.controller` e `{base_package}.api.routes` (skill
    01 — os dois lugares onde um módulo pode ter rota própria).
    """
    from flask import Blueprint

    blueprints: list = []
    seen_ids: set[int] = set()
    for sub_package in ("controller", "api.routes"):
        for module in _walk_package_modules(f"{base_package}.{sub_package}"):
            for attr_name in dir(module):
                attr = getattr(module, attr_name, None)
                if isinstance(attr, Blueprint) and id(attr) not in seen_ids:
                    seen_ids.add(id(attr))
                    blueprints.append(attr)
    return blueprints


def discover_features(addon_module_dir: Path, addon_dotted_package: str, addon_table_prefix: str) -> list:
    """
    Adenda skill 09 (achado durante a implementação do Patch B da
    skill 06): `get_features()` também era 100% manual — mesmo
    problema que `register_models()`/`register_routes()` tinham antes
    desta skill, só que um nível acima. Mesmo mecanismo de
    `ModuleManager.discover_and_register_addons()` (escaneia
    `addon_*/addon.json`+`addon.py`), aplicado a `features/feature_*/
    feature.json`+`feature.py` — cada Feature encontrada é importada e
    instanciada, exatamente como um Addon.

    Import feito via caminho pontuado normal (`addons.addon_X.features.
    feature_Y.feature`), não via spec_from_file_location como
    discover_and_register_addons faz para addon.py — porque aqui
    `addon_dotted_package` já é sempre um pacote real, nunca o próprio
    arquivo lido dinamicamente.
    """
    features_dir = addon_module_dir / "features"
    if not features_dir.is_dir():
        return []

    discovered = []
    for feature_dir in sorted(features_dir.glob("feature_*")):
        manifest_path = feature_dir / "feature.json"
        feature_py_path = feature_dir / "feature.py"
        if not manifest_path.exists() or not feature_py_path.exists():
            continue

        try:
            import json
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception(
                "Falha ao ler %s durante auto-descoberta de Features (skill 09) "
                "— pulando esta Feature.", manifest_path,
            )
            continue

        dotted_module = f"{addon_dotted_package}.features.{feature_dir.name}.feature"
        try:
            py_module = importlib.import_module(dotted_module)
        except Exception:
            logger.exception(
                "Falha ao importar %s durante auto-descoberta de Features "
                "(skill 09) — pulando esta Feature.", dotted_module,
            )
            continue

        class_name = getattr(py_module, "__module__", None)
        if not class_name or not hasattr(py_module, class_name):
            logger.warning(
                "%s: __module__ não declarado ou classe não encontrada — "
                "ignorando na auto-descoberta de Features.", feature_dir.name,
            )
            continue

        feature_class = getattr(py_module, class_name)
        try:
            discovered.append(feature_class(manifest, addon_table_prefix=addon_table_prefix))
        except Exception:
            logger.exception(
                "Falha ao instanciar Feature de %s na auto-descoberta (skill 09).",
                feature_dir.name,
            )
    return discovered


def find_route_for_endpoint(endpoint: str) -> str | None:
    """
    Confirma que uma rota existe de verdade antes de gerar Transação
    automática para ela (mesmo espírito do try/except url_for() do
    PyTeca) — usa current_app.url_map diretamente em vez de url_for()
    porque este código roda no boot, dentro de app_context mas fora de
    qualquer request_context, onde url_for() para blueprints com
    url_prefix nem sempre resolve de forma confiável.
    """
    from flask import current_app

    for rule in current_app.url_map.iter_rules():
        if rule.endpoint == endpoint:
            return rule.rule
    return None


def _slugify_code(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name or "").strip("_").upper()
    slug = re.sub(r"_+", "_", slug)
    return slug or "MODULO"


def auto_transactions_from_models(models: list[type], *, module_name: str, module_label: str) -> list[dict]:
    """
    Gera entradas de Transação a partir de models já descobertos —
    convenção definida na skill 00 (adendo skill 09) + skill 10
    (árvore): cria (ou reaproveita, via sync idempotente) uma pasta
    própria por módulo, código `TX_GROUP_AUTO_<MODULO>` — namespace
    separado de `TX_GROUP_` (manual), pra nunca colidir sozinho com um
    grupo curado à mão; quem quiser unificar sobrescreve
    get_transactions() apontando parent_code pro grupo manual direto.

    `code=TX_AUTO_<PLURAL>`, `icon=@menu_icon ou "bi-app"`. Só inclui
    o model se a rota de listagem (`{plural}.list`, convenção do
    CrudGen) realmente existir — nunca um item de menu morto.
    """
    from annotations import get_model_metadata

    leaf_entries = []
    for model_cls in models:
        meta = get_model_metadata(model_cls)
        plural = meta.get("plural")
        label = meta.get("label")
        if not plural or not label:
            continue

        route = find_route_for_endpoint(f"{plural}.list")
        if not route:
            continue

        leaf_entries.append({
            "code": f"TX_AUTO_{plural.upper()}",
            "label": label,
            "icon": meta.get("menu_icon") or "bi-app",
            "route": route,
            "permission_required": f"{plural}.list",
        })

    if not leaf_entries:
        return []

    folder_code = f"TX_GROUP_AUTO_{_slugify_code(module_name)}"
    folder_entry = {
        "code": folder_code,
        "label": module_label,
        "parent_code": None,
        "route": None,
        "icon": "bi-folder2",
    }
    for entry in leaf_entries:
        entry["parent_code"] = folder_code

    return [folder_entry] + leaf_entries
