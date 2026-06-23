"""
core/crudgen/manifest_utils.py

Lê addon.json/feature.json em disco e calcula o prefixo de tabela
tri-nível completo (skill 02). Nenhuma outra parte do CrudGen lê
manifesto diretamente — só por aqui.
"""
import json
from pathlib import Path


class ManifestError(ValueError):
    pass


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise ManifestError(f"Manifesto não encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_table_prefix(project_root: Path, addon: str, feature: str | None = None) -> str:
    """
    Retorna o prefixo completo SEM o "tesseract_" inicial (esse é
    aplicado separadamente) — ex.: "brewstation" ou
    "brewstation_yeastbank".
    """
    addon_json = project_root / "addons" / f"addon_{addon}" / "addon.json"
    addon_manifest = _read_json(addon_json)

    table_prefix = addon_manifest.get("table_prefix")
    if not table_prefix:
        raise ManifestError(
            f"addon.json de '{addon}' não tem 'table_prefix' (skill 03)."
        )

    if feature is None:
        return table_prefix

    feature_json = (
        project_root / "addons" / f"addon_{addon}" / "features"
        / f"feature_{feature}" / "feature.json"
    )
    feature_manifest = _read_json(feature_json)
    suffix = feature_manifest.get("table_prefix_suffix")
    if not suffix:
        raise ManifestError(
            f"feature.json de '{feature}' não tem 'table_prefix_suffix' (skill 02/03)."
        )
    return f"{table_prefix}_{suffix}"


def resolve_output_dir(project_root: Path, addon: str, feature: str | None = None) -> Path:
    base = project_root / "addons" / f"addon_{addon}"
    if feature is None:
        return base / "root"
    return base / "features" / f"feature_{feature}"
