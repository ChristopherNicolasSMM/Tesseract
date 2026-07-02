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
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
    module_name = type(obj).__module__
    mod = sys.modules.get(module_name)
    if not mod or not getattr(mod, "__file__", None):
        logger.debug(
            "own_base_package: não foi possível resolver __file__ de %s "
            "(module_name=%s) — auto-descoberta não vai encontrar nada "
            "para esta instância.", obj, module_name,
        )
        return None

    module_dir = Path(mod.__file__).resolve().parent
    base_dir = module_dir / "root" if (module_dir / "root").is_dir() else module_dir

    try:
        rel = base_dir.relative_to(_PROJECT_ROOT)
    except ValueError:
        logger.warning(
            "own_base_package: %s está fora de %s — auto-descoberta pulada.",
            base_dir, _PROJECT_ROOT,
        )
        return None

    return ".".join(rel.parts), base_dir


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


def auto_transactions_from_models(models: list[type], *, group_label: str) -> list[dict]:
    """
    Gera entradas de Transação a partir de models já descobertos —
    convenção `code`/`group`/`icon` definida na skill 00 (adendo
    skill 09): `code=TX_AUTO_<PLURAL>`, `group=<label do módulo dono>`,
    `icon=@menu_icon ou "bi-app"`. Só inclui o model se a rota de
    listagem (`{plural}.list`, convenção do CrudGen) realmente existir
    — nunca um item de menu morto.
    """
    from annotations import get_model_metadata

    transactions = []
    for model_cls in models:
        meta = get_model_metadata(model_cls)
        plural = meta.get("plural")
        label = meta.get("label")
        if not plural or not label:
            continue

        route = find_route_for_endpoint(f"{plural}.list")
        if not route:
            continue

        transactions.append({
            "code": f"TX_AUTO_{plural.upper()}",
            "label": label,
            "group": group_label,
            "icon": meta.get("menu_icon") or "bi-app",
            "route": route,
            "permission_required": f"{plural}.list",
        })
    return transactions
