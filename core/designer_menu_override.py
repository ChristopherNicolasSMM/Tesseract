"""
core/designer_menu_override.py

Fase 10, Patch 6 — resolver do checkbox DesignerPage.replace_in_menu:
troca o item de MENU (Transaction.route) de uma tela do CrudGen pela
rota da DesignerPage publicada que a substitui. A rota original do
CrudGen nunca é tocada nem desregistrada (decisão registrada em
BACKLOG.md, Fase 10) — quem digitar a URL antiga na mão continua
vendo a tela crua do CrudGen, pra debug/conferência de valores.

Convenção de `replaces_entity_key` (achado real, corrigido nesta
fase — ver comentário em model/core/designer_page.py): é o PLURAL, o
mesmo já usado em FieldRule.entity_key, UserListPreference.list_key
e no prefixo de Permission de toda entidade do CrudGen (ex.:
"yeast_strains"). A Transaction candidata é encontrada por
`permission_required == "<replaces_entity_key>.list"` — mesmo padrão
de permissão automática (Camada 1) que o CrudGen já sincroniza pra
toda entidade gerada.

Só `replaces_view == "manage"` tem Transaction de menu pra trocar —
uma tela de "detail" nunca vira item de menu por conta própria (é
acessada por link dentro do "manage"), então não há o que resolver
aqui pra ela ainda; o campo já existe no schema, pronto pra quando um
mecanismo de override de link "ver detalhe" existir.

Idempotente e sempre parte de um resync completo (código lidera,
banco segue — skill 00/10): nunca tenta "lembrar" qual era a rota
original de uma Transaction — reconstrói do zero a cada chamada
(sync_all_transactions + sync_core_transactions, os mesmos que já
rodam no boot) e só então reaplica os overrides ainda válidos. Isso
faz a reversão (despublicar a página, desmarcar o checkbox, apagar a
página) acontecer sozinha, sem precisar guardar estado nenhum — só
roda quando um admin mexe numa DesignerPage ou no boot, nunca por
requisição normal, então o custo do resync completo não é um
problema real aqui.
"""
import logging

from flask import current_app

from core.db import db
from model.core.designer_page import DesignerPage
from model.core.transaction import Transaction

logger = logging.getLogger(__name__)


def resolve_designer_page_menu_overrides() -> None:
    from core.transactions_sync import sync_core_transactions

    current_app.module_manager.sync_all_transactions()
    sync_core_transactions()

    applied = []
    pages = DesignerPage.query.filter_by(is_published=True, replace_in_menu=True).all()
    for page in pages:
        if not page.replaces_entity_key or page.replaces_view != "manage":
            continue
        tx = Transaction.query.filter_by(
            permission_required=f"{page.replaces_entity_key}.list"
        ).first()
        if tx is None:
            logger.warning(
                "DesignerPage id=%s (slug=%s) marcou replace_in_menu para "
                "entity_key=%r, mas nenhuma Transaction com "
                "permission_required=%r foi encontrada — nada trocado.",
                page.id, page.slug, page.replaces_entity_key,
                f"{page.replaces_entity_key}.list",
            )
            continue
        tx.route = f"/designer/{page.slug}"
        applied.append((page.slug, tx.code))

    db.session.commit()
    if applied:
        logger.info("Menu sobrescrito por DesignerPage publicada: %s", applied)
