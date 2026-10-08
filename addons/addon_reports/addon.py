"""Addon de relatórios em construção; sem publicar capacidades incompletas."""
__module__ = "AddonReports"

from core.addon_base import AddonBase


class AddonReports(AddonBase):
    def get_transactions(self):
        return [{'code': 'TX_REPORT_TEMPLATES', 'label': 'Relatórios',
                 'route': '/reports/', 'icon': 'bi-file-earmark-pdf',
                 'permission_required': 'report_templates.list'}]
