"""
core/odata_provider/

Fase 10, Patch 2 — provedor OData do próprio Tesseract, servindo
entidades marcadas com @odata_expose (annotations/__init__.py) tanto
via HTTP real (api/routes/core/odata_provider.py, para consumidores
externos ou o atalho em processo do próprio Designer) quanto direto
em processo (service.py), sem round-trip de rede, usado pelo atalho
registrado em core/odata/connection_manager.py quando
ODataConnection.is_local=True.
"""
