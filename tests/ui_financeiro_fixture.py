"""Servidor de respostas Flask em memória para teste do navegador via stdio."""
import contextlib
import json
import sys
import base64
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with contextlib.redirect_stdout(sys.stderr):
    from core.app_factory import create_app
    from core.db import db
    from model.core.user import User
    from services.core.organization_service import save_organization
    from plugins.plugin_getcep.provider import LookupError
    app=create_app(env='testing')
    with app.app_context():
        user=User(username='ui_admin',email='ui@test.local',nome='Admin',nome_completo='Admin',celular='11999999999',is_admin=True,is_active=True)
        user.set_password('senha123');db.session.add(user);db.session.commit()
        save_organization({'code':'UI_ORG','name':'Organização existente','legal_name':'Razão persistida','email':'org@test.local','is_active':True})
    def lookup(cep):
        from core.document_validation import DocumentValidator
        cep=DocumentValidator.cep(cep)
        if cep=='99999999':raise LookupError('CEP não encontrado.',404)
        if cep=='88888888':raise LookupError('Consulta CEP indisponível.',503)
        return {'cep':cep,'logradouro':'Praça da Sé','bairro':'Sé','cidade':'São Paulo','estado':'SP'}
    app.extensions['getcep_provider'].lookup=lookup
    client=app.test_client()
    client.post('/api/auth/login',json={'username':'ui_admin','password':'senha123'})
print(json.dumps({'ready':True}),flush=True)
for line in sys.stdin:
    command=json.loads(line)
    try:
        with contextlib.redirect_stdout(sys.stderr):
            response=client.open(command['path'],method=command.get('method','GET'),data=base64.b64decode(command.get('body','')),headers=command.get('headers',{}),follow_redirects=True)
        print(json.dumps({'id':command['id'],'status':response.status_code,'headers':dict(response.headers),'body':base64.b64encode(response.data).decode()}),flush=True)
    except Exception as exc:
        print(json.dumps({'id':command['id'],'error':str(exc)}),flush=True)
