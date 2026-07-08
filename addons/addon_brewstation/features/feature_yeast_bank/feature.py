"""
addons/addon_brewstation/features/feature_yeast_bank/feature.py
"""
__module__ = "FeatureYeastBank"

from core.feature_base import FeatureBase


class FeatureYeastBank(FeatureBase):
    # register_models()/register_routes() migrados pro caminho de
    # auto-descoberta (skill 09) nesta sessão — o default de
    # FeatureBase já cobre os 8 models de model/ e os Blueprints de
    # controller/+api/routes/ (inclusive yeast_bank_viability_bp,
    # hand-written). get_transactions() continua manual de propósito
    # (BACKLOG.md — auto-descoberta perderia labels/ícones/descrições
    # curados e o código TX_ mudaria).

    def get_transactions(self) -> list:
        return [
            {
                "code": "TX_GROUP_YEAST_BANK",
                "label": "Banco de Levedura",
                "parent_code": "TX_GROUP_BREWSTATION",  # skill 10 secao 7.1 - agrupa sob o Addon pai
                "route": None,
                "icon": "bi-droplet-fill",
            },
            {
                "code": "TX_YEAST_BANK",
                "label": "Cepas de Levedura",
                "parent_code": "TX_GROUP_YEAST_BANK",
                "description": "Cadastro e acompanhamento de cepas de levedura.",
                "icon": "bi-droplet-fill",
                "route": "/brewstation/yeast-strains",
                "permission_required": "yeast_strains.list",
            },
            {
                "code": "TX_YEAST_BANK_ITEMS",
                "label": "Itens do Banco",
                "parent_code": "TX_GROUP_YEAST_BANK",
                "description": "Itens físicos do banco (slants, placas, salinas).",
                "icon": "bi-box-seam",
                "route": "/brewstation/yeast-bank-items",
                "permission_required": "yeast_bank_items.list",
            },
            {
                "code": "TX_YEAST_STORAGE_DEVICES",
                "label": "Dispositivos de Armazenamento",
                "parent_code": "TX_GROUP_YEAST_BANK",
                "description": "Freezers/geladeiras usados para guardar o banco.",
                "icon": "bi-snow",
                "route": "/brewstation/yeast-storage-devices",
                "permission_required": "yeast_storage_devices.list",
            },
            {
                "code": "TX_YEAST_STORAGE_READINGS",
                "label": "Leituras de Temperatura",
                "parent_code": "TX_GROUP_YEAST_BANK",
                "description": "Histórico de temperatura dos dispositivos de armazenamento.",
                "icon": "bi-thermometer-snow",
                "route": "/brewstation/yeast-storage-readings",
                "permission_required": "yeast_storage_readings.list",
            },
            {
                "code": "TX_YEAST_STARTER_LOGS",
                "label": "Starters",
                "parent_code": "TX_GROUP_YEAST_BANK",
                "description": "Propagação/starters realizados a partir de um item do banco.",
                "icon": "bi-flask",
                "route": "/brewstation/yeast-starter-logs",
                "permission_required": "yeast_starter_logs.list",
            },
            {
                "code": "TX_YEAST_CELL_COUNT_HISTORIES",
                "label": "Contagens de Células",
                "parent_code": "TX_GROUP_YEAST_BANK",
                "description": "Histórico de contagem de células e viabilidade real/estimada.",
                "icon": "bi-grid-3x3",
                "route": "/brewstation/yeast-cell-count-histories",
                "permission_required": "yeast_cell_count_histories.list",
            },
            {
                "code": "TX_YEAST_BANK_EVENTS",
                "label": "Eventos do Banco",
                "parent_code": "TX_GROUP_YEAST_BANK",
                "description": "Linha do tempo de eventos de um item do banco.",
                "icon": "bi-calendar-event",
                "route": "/brewstation/yeast-bank-events",
                "permission_required": "yeast_bank_events.list",
            },
            {
                "code": "TX_YEAST_BANK_CONFIGS",
                "label": "Configurações do Banco",
                "parent_code": "TX_GROUP_YEAST_BANK",
                "description": "Parâmetros gerais do banco de levedura.",
                "icon": "bi-sliders",
                "route": "/brewstation/yeast-bank-configs",
                "permission_required": "yeast_bank_configs.list",
            },
            {
                "code": "TX_YEAST_BANK_RECALC_VIABILITY",
                "label": "Recalcular Viabilidade",
                "parent_code": "TX_GROUP_YEAST_BANK",
                "description": "Recalcula a viabilidade estimada de todos os itens do banco.",
                "icon": "bi-arrow-repeat",
                "route": "/brewstation/yeast-bank-tools/recalculate-viability",
                "permission_required": "yeast_bank_items.recalculate_viability",
            },
        ]

