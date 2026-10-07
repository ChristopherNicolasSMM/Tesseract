from core.addon_base import AddonBase
__module__ = 'AddonFinanceiro'


class AddonFinanceiro(AddonBase):
    def get_transactions(self):
        return [{'code': 'FIN_SETUP', 'label': 'Configuração financeira', 'route': '/financeiro/',
                 'permission_required': 'admin', 'icon': 'bi-currency-exchange', 'group': 'Financeiro'}]
