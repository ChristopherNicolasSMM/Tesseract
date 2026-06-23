"""
core/template_loader.py

ChoiceLoader mesclando templates do core com os de cada Addon/Plugin
ativo. Portado do padrão já usado no BrewStation. O Core sempre vem
primeiro na cadeia (resolve antes), depois os módulos na ordem em que
foram ativados.
"""
import logging
import os

from jinja2 import ChoiceLoader, FileSystemLoader

logger = logging.getLogger(__name__)


def build_template_loader(app, active_template_dirs: list[str]) -> ChoiceLoader:
    """
    active_template_dirs: lista de caminhos absolutos de pasta
    `templates/` de cada Addon/Plugin ativo, na ordem de ativação.
    """
    loaders = [app.jinja_loader]  # templates/core/ (padrão do Flask)
    for path in active_template_dirs:
        if os.path.isdir(path):
            loaders.append(FileSystemLoader(path))
            logger.debug("Template dir registrado: %s", path)
        else:
            logger.warning("Template dir inexistente, ignorado: %s", path)

    return ChoiceLoader(loaders)
