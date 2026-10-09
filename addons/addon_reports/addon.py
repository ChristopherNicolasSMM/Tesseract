"""Addon de relatórios com descoberta padrão de rotas, modelos e menu."""
__module__ = "AddonReports"

from core.addon_base import AddonBase


class AddonReports(AddonBase):
    """Transações geradas pelas anotações e endpoints do CrudGen."""

    def get_transactions(self):
        from addons.addon_reports.root.services.report_emission_service import catalog_transactions
        return super().get_transactions() + catalog_transactions()
