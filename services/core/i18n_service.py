"""
services/core/i18n_service.py

Primeiro corte real do motor de resolução de i18n (skill 00, Adendo
"Motor de resolução de i18n"). Nasceu escopado para servir a skill 15
(diálogo de confirmação / toast) — não migra o projeto inteiro de uma
vez, só resolve `translate()` para quem passar a chamar.

Carrega e faz merge de:
- core/i18n/[locale].json (chaves genéricas de Core, ex. "core.*")
- i18n/[locale].json de cada Addon/Feature/Plugin ATIVO (ModuleManager)

Locale: fixo em "pt_BR" neste corte (available_locales sempre ["pt_BR"]
em todo manifesto hoje — skill 00/03). Parâmetro `locale` já existe na
assinatura para não exigir mudança de assinatura quando um segundo
idioma real existir.
"""
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_LOCALE = "pt_BR"

# Cache em memória — recarregado só quando reset_cache() é chamado
# (ModuleManager deve chamar isso ao ativar/desativar um módulo, mesmo
# espírito do cache de template_dirs já existente).
_translations_cache: dict[str, dict[str, str]] = {}


def _core_i18n_dir() -> Path:
    # services/core/i18n_service.py -> services/core -> services -> raiz
    return Path(__file__).resolve().parent.parent.parent / "core" / "i18n"


def _module_dir_for(module_obj) -> Path | None:
    """
    Mesma técnica de resolução de `core/module_manager.py::_template_dir_for`
    (via __module__ -> sys.modules -> __file__), mas devolvendo a pasta
    base do módulo (Addon/Feature/Plugin), não a de templates — quem
    chama decide se olha `root/i18n` (Addon) ou `i18n` (Feature/Plugin).
    """
    module_name = type(module_obj).__module__
    mod = sys.modules.get(module_name)
    if not mod or not getattr(mod, "__file__", None):
        return None
    return Path(mod.__file__).parent


def _i18n_dir_for(module_obj) -> Path | None:
    base = _module_dir_for(module_obj)
    if base is None:
        return None
    root_i18n_dir = base / "root" / "i18n"
    if root_i18n_dir.is_dir():
        return root_i18n_dir
    i18n_dir = base / "i18n"
    return i18n_dir if i18n_dir.is_dir() else None


def _load_json(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("i18n_service: falha ao ler %s (%s)", path, exc)
        return {}


def _build_translations(app, locale: str) -> dict[str, str]:
    merged: dict[str, str] = {}

    core_file = _core_i18n_dir() / f"{locale}.json"
    if core_file.is_file():
        merged.update(_load_json(core_file))

    module_manager = getattr(app, "module_manager", None)
    if module_manager is not None:
        for module_obj in module_manager.active_modules.values():
            i18n_dir = _i18n_dir_for(module_obj)
            if i18n_dir is None:
                continue
            module_file = i18n_dir / f"{locale}.json"
            if module_file.is_file():
                merged.update(_load_json(module_file))

    return merged


def reset_cache() -> None:
    """Chamado pelo ModuleManager ao ativar/desativar um módulo, e nos
    testes (cada app de teste tem seu próprio conjunto de módulos
    ativos)."""
    _translations_cache.clear()


def all_translations(locale: str | None = None) -> dict[str, str]:
    """
    Dicionário completo do locale resolvido — usado por
    `templates/core/base.html` para expor as traduções ao JS
    (`window.__tesseractTranslations`), já que `data-confirm-key`
    (skill 15) precisa do texto no cliente sem round-trip ao servidor
    a cada clique.
    """
    from flask import current_app

    resolved_locale = locale or DEFAULT_LOCALE
    if resolved_locale not in _translations_cache:
        _translations_cache[resolved_locale] = _build_translations(current_app, resolved_locale)
    return dict(_translations_cache[resolved_locale])


def translate(key: str, locale: str | None = None, **params) -> str:
    """
    Resolve `key` para o texto no locale ativo (fixo em pt_BR neste
    corte). Interpolação via `{param}` na string armazenada.

    Chave ausente em todo lugar (não é o caso de "locale secundário sem
    tradução" coberto pela regra de ouro original da skill 00): loga
    aviso no log global e retorna a própria chave como fallback visível
    — torna o erro de digitação/chave esquecida visível em vez de
    mascarado.
    """
    from flask import current_app

    resolved_locale = locale or DEFAULT_LOCALE

    if resolved_locale not in _translations_cache:
        _translations_cache[resolved_locale] = _build_translations(current_app, resolved_locale)

    text = _translations_cache[resolved_locale].get(key)

    if text is None and resolved_locale != DEFAULT_LOCALE:
        if DEFAULT_LOCALE not in _translations_cache:
            _translations_cache[DEFAULT_LOCALE] = _build_translations(current_app, DEFAULT_LOCALE)
        text = _translations_cache[DEFAULT_LOCALE].get(key)

    if text is None:
        logger.warning("i18n_service: chave ausente em todo locale: %s", key)
        return key

    try:
        return text.format(**params) if params else text
    except (KeyError, IndexError) as exc:
        logger.warning("i18n_service: falha ao interpolar '%s' (%s)", key, exc)
        return text
