"""Consulta de CEP sob demanda, sem persistência e sem URLs fornecidas pelo usuário."""
from collections import OrderedDict
import json
from threading import Lock
from time import monotonic
import requests
from core.document_validation import DocumentValidator


class LookupError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


class ViaCEP:
    def __init__(self, *, transport=None, clock=monotonic):
        self.transport = transport or requests.get
        self.clock = clock
        self.cache = OrderedDict()
        self.lock = Lock()

    def lookup(self, cep):
        cep = DocumentValidator.cep(cep)
        with self.lock:
            entry = self.cache.get(cep)
            if entry and entry[0] > self.clock():
                self.cache.move_to_end(cep)
                return dict(entry[1])
            self.cache.pop(cep, None)
        # Fixed host, no redirects. Streaming caps response before JSON decode.
        try:
            with self.transport(f'https://viacep.com.br/ws/{cep}/json/', timeout=(2, 3),
                                allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    raise LookupError('Consulta CEP indisponível. Preencha o endereço manualmente.')
                raw = bytearray()
                for chunk in response.iter_content(chunk_size=2048):
                    raw.extend(chunk)
                    if len(raw) > 16384:
                        raise LookupError('Resposta do serviço CEP excede o limite.')
                payload = json.loads(raw.decode('utf-8'))
            if not isinstance(payload, dict):
                raise LookupError('Resposta inválida do serviço CEP.')
            if payload.get('erro') in (True, 'true'):
                raise LookupError('CEP não encontrado. Confira ou preencha manualmente.', 404)
            if DocumentValidator.cep(payload.get('cep')) != cep:
                raise LookupError('CEP retornado não corresponde à consulta.')
            fields = {'logradouro': ('logradouro', 200), 'bairro': ('bairro', 100),
                      'cidade': ('localidade', 100), 'estado': ('uf', 2)}
            address = {'cep': cep}
            for field, (source, limit) in fields.items():
                value = payload.get(source)
                if not isinstance(value, str) or len(value) > limit:
                    raise LookupError('Resposta inválida do serviço CEP.')
                address[field] = value
            if address['estado'] not in 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split() or not address['cidade']:
                raise LookupError('Cidade ou UF inválida no serviço CEP.')
        except (requests.RequestException, UnicodeError, ValueError) as exc:
            raise LookupError('Consulta CEP indisponível. Preencha o endereço manualmente.') from exc
        with self.lock:
            self.cache[cep] = (self.clock() + 3600, dict(address))
            self.cache.move_to_end(cep)
            while len(self.cache) > 256:
                self.cache.popitem(last=False)
        return address
