"""
model/core/designer_page.py

tesseract_designer_page — página customizada, escrita à mão.

Histórico: nasceu na Fase 7c como página montada por drag-and-drop
(canvas + DesignerComponent), e a Fase 11 chegou a implementar árvore
de componentes e catálogo de propriedades. Na Fase 12 o construtor
visual foi REMOVIDO por decisão de escopo — construtor visual é um
produto inteiro, não uma feature, e para um time onde quem monta as
telas já programa, escrever HTML é mais rápido e previsível do que
arrastar caixas. O que ficou é o essencial e estável: um cadastro de
páginas customizadas com conteúdo HTML próprio, servido pelo runtime,
podendo substituir uma tela do CrudGen no menu.

`content_html` é renderizado como HTML confiável (|safe), nunca como
template Jinja — renderizar Jinja vindo do banco seria injeção de
template (SSTI), que na prática é execução de código no servidor,
mesmo restrito a admin. Para dado dinâmico, a página usa JavaScript
chamando as Ações de Dado (POST /admin/designer/data-action/<id>/execute)
ou a API do próprio Tesseract.
"""
from datetime import datetime, timezone

from core.db import db


class DesignerPage(db.Model):
    __tablename__ = "tesseract_designer_page"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False, default="Página")
    title = db.Column(db.String(200), nullable=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)

    # Corpo da página, escrito à mão. Ver static/modelo_paginas_nice_admin/
    # _modelo-pagina-customizada.html para o ponto de partida com os
    # componentes do NiceAdmin já no padrão do sistema.
    content_html = db.Column(db.Text, nullable=True)

    is_published = db.Column(db.Boolean, default=False, nullable=False)
    permission_required = db.Column(db.String(150), nullable=True)

    # Fase 10 (Patch 1, schema; Patch 6, resolver real — skill 16).
    # Referência fraca (nunca FK — skill 02). Achado real corrigido no
    # Patch 6: o valor esperado é o PLURAL — mesmo formato de
    # FieldRule.entity_key, UserListPreference.list_key e do prefixo
    # de Permission de toda entidade do CrudGen (ex.: "yeast_strains",
    # não "yeast_strain") — é contra essa convenção que
    # core/designer_menu_override.py resolve a Transaction a trocar
    # (via permission_required == "<replaces_entity_key>.list").
    replaces_entity_key = db.Column(db.String(150), nullable=True)
    replaces_view = db.Column(db.String(20), nullable=True)  # "manage" | "detail"
    # Checkbox: só tem efeito com replaces_entity_key preenchido e
    # replaces_view == "manage" (só a tela de listagem vira item de
    # menu por conta própria — "detail" nunca tem Transaction própria
    # pra trocar). True = a rota original do CrudGen some do MENU
    # (nunca da aplicação — continua acessível direto, por decisão
    # registrada em BACKLOG.md/skill 16, para permitir debug/
    # conferência de valores).
    replace_in_menu = db.Column(db.Boolean, default=False, nullable=False)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self, include_content: bool = False) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "title": self.title or self.name,
            "slug": self.slug,
            "is_published": self.is_published,
            "permission_required": self.permission_required,
            "replaces_entity_key": self.replaces_entity_key,
            "replaces_view": self.replaces_view,
            "replace_in_menu": self.replace_in_menu,
        }
        if include_content:
            d["content_html"] = self.content_html or ""
        return d

    def __repr__(self) -> str:
        return f"<DesignerPage id={self.id} name={self.name!r} slug={self.slug!r}>"
