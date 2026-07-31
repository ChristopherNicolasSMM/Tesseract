"""
model/core/odata_connection.py

tesseract_odata_connection — conexão a um servidor OData V4 externo,
com cache de metadata. Adaptado de models/odata_connection.py
(DEVStationFlask) — sem `project_id`: o DEVStationFlask original
escopava conexões por "Projeto" (do Designer dele); o Tesseract não
tem esse conceito ainda, então a conexão é global (qualquer usuário
com permissão vê todas).

Core, não Addon/Feature — é infraestrutura de integração, não dado
de domínio de cervejaria.
"""
from datetime import datetime, timezone

from core.db import db


class ODataConnection(db.Model):
    __tablename__ = "tesseract_odata_connection"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    base_url = db.Column(db.String(500), nullable=False)

    auth_type = db.Column(db.String(20), default="none", nullable=False)  # none | basic | bearer
    auth_value = db.Column(db.String(500), nullable=True)  # token ou "user:pass"

    metadata_cache = db.Column(db.JSON, nullable=True)
    metadata_cached_at = db.Column(db.DateTime, nullable=True)

    # Correção de bug (BACKLOG.md, "Bugs de OData"): para servidores
    # cujo metadata não declara EntitySet (formato customizado
    # "S2MOdataPy"), não há como derivar o nome real da rota de
    # coleção só a partir do metadata. Guarda o mapeamento
    # {nome_declarado: nome_real_resolvido}, preenchido automaticamente
    # por tentativa (pluralização heurística) ou manualmente pela tela
    # "Ver entidades". Nunca sobrescrito por um refresh de metadata_cache.
    entity_route_overrides = db.Column(db.JSON, nullable=True)

    # Fase 10 (Patch 1) — marca a conexão auto-seedada (idempotente,
    # ver core/odata_local_seed.py) que representa o provedor OData do
    # próprio Tesseract, servindo entidades do CrudGen marcadas com
    # @odata_expose (annotations/__init__.py). Uma Ação de Dado
    # (tesseract_designer_data_action) que aponta para uma conexão com
    # is_local=True pula a chamada HTTP real e executa em processo,
    # direto contra o provedor local — mesmo contrato de entrada/saída
    # de ODataConnectionManager.query()/patch(), sem o round-trip de
    # rede (decisão registrada em BACKLOG.md, Fase 10).
    is_local = db.Column(db.Boolean, default=False, nullable=False)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "base_url": self.base_url,
            "auth_type": self.auth_type,
            "is_local": self.is_local,
            "has_metadata_cache": self.metadata_cache is not None,
            "metadata_cached_at": self.metadata_cached_at.isoformat() if self.metadata_cached_at else None,
            "entity_route_overrides": self.entity_route_overrides or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<ODataConnection id={self.id} name={self.name!r} url={self.base_url!r}>"
