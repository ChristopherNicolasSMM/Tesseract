"""
model/core/designer_data_action.py

tesseract_designer_data_action — "Ação de Dado" (Fase 10, Patch 1):
configuração reutilizável de acesso a dado via uma ODataConnection
(externa, tipo BrewFather, ou local, tipo o próprio Tesseract via
ODataConnection.is_local) — nunca digitada à mão duas vezes, mesmo
princípio de tabela-de-configuração já usado por FieldRule e
ODataConnection (skill 00, regra de ouro do usuário: "tudo que for
configuração fica em tabela").

Sempre executada server-side (decisão registrada em BACKLOG.md, Fase
10) — nunca client-side, porque a conexão pode envolver credencial
(.env, via ODataConnection.auth_value). A ligação evento -> Ação de
Dado fica em DesignerComponent.events (JSON já existente, Fase 7c),
referenciando o id desta tabela — não duplica lógica aqui.

Execução real (chamar ODataConnectionManager, ou pular pro atalho
direto-em-processo quando connection.is_local=True) é peça do Patch 3
(core/actions_catalog.py + engine de execução) — este model é só o
schema desta configuração.
"""
from datetime import datetime, timezone

from core.db import db

OPERATIONS = ("query", "create", "update", "delete")


class DesignerDataAction(db.Model):
    __tablename__ = "tesseract_designer_data_action"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(300), nullable=True)

    # FK interna Core -> Core, sempre permitida (skill 02). Nunca nula
    # — mesmo para dado local, aponta para a ODataConnection auto-
    # seedada com is_local=True (core/odata_local_seed.py).
    connection_id = db.Column(db.Integer, db.ForeignKey("tesseract_odata_connection.id"), nullable=False)

    entity_name = db.Column(db.String(100), nullable=False)
    operation = db.Column(db.String(20), nullable=False, default="query")

    # Parâmetros fixos aplicados sempre, independente do componente que
    # dispara a Ação (ex.: um $filter que nunca muda) — mesmo padrão de
    # DesignerComponent.properties (JSON livre, sem schema próprio).
    static_params = db.Column(db.JSON, default=lambda: {})

    # Mesmo padrão de DesignerPage.permission_required (Role via
    # User.has_permission()) — NULL = público (decisão registrada em
    # BACKLOG.md, Fase 10: sem permissão por usuário individual nesta
    # fase, só por grupo/Role, que já existe).
    permission_required = db.Column(db.String(150), nullable=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    connection = db.relationship("ODataConnection")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "connection_id": self.connection_id,
            "entity_name": self.entity_name,
            "operation": self.operation,
            "static_params": self.static_params or {},
            "permission_required": self.permission_required,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<DesignerDataAction id={self.id} name={self.name!r} entity={self.entity_name!r}>"
