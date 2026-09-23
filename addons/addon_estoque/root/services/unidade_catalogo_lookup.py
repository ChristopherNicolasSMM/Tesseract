"""Resolver de referência fraca para campos que guardam o código da unidade."""
from addons.addon_estoque.root.model.unidade_catalogo import UnidadeCatalogo


def get_unidade(codigo):
    return UnidadeCatalogo.query.filter_by(codigo=codigo, is_deleted=False).first()
