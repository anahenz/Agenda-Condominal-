import copy
import json
import uuid
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from app.services.agenda import AgendaService, filter_events
from app.utils.wire import encode, decode


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class ApiClient:
    def __init__(self, url, token='', allow_local=False):
        parsed = urlsplit(url.strip())
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Informe somente o endereço HTTPS do servidor.')
        if parsed.scheme != 'https' and not (allow_local and parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost')):
            raise ValueError('O servidor deve usar HTTPS.')
        if not parsed.hostname or parsed.path not in ('', '/'):
            raise ValueError('Use a URL principal, sem caminho adicional.')
        self.url = url.strip().rstrip('/')
        self.token = token
        self.user = {}

    def request(self, path, data=None, method=None, raw=False):
        headers = {'Accept': 'application/json'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        if isinstance(data, bytes):
            body = data
            headers['Content-Type'] = 'application/octet-stream'
        elif data is not None:
            body = json.dumps(encode(data)).encode()
            headers['Content-Type'] = 'application/json'
        else:
            body = None
        req = Request(self.url + path, data=body, headers=headers, method=method)
        try:
            with build_opener(NoRedirect()).open(req, timeout=30) as response:
                content = response.read()
                if raw:
                    return content
                result = decode(json.loads(content))
                if path == '/v1/snapshot' and (not isinstance(result, dict) or not {'events','condos','audit','revision'}.issubset(result)):
                    raise ValueError('Este endereço não é um servidor da AgendaCondominial. Use a URL da agenda, não a do ContasPagar.')
                return result
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read()).get('detail', '')
                if not isinstance(detail, str):
                    detail = 'Confira os campos informados.'
            except Exception:
                detail = 'O servidor recusou a solicitação.'
            raise ValueError(detail or f'Erro HTTP {exc.code}.') from None
        except (URLError, TimeoutError, OSError):
            raise ValueError('Sem conexão com o servidor. Confira sua internet. Se estava salvando, atualize a lista antes de tentar novamente para conferir se a operação foi concluída.') from None

    def login(self, email, password):
        result = self.request('/v1/login', {'email': email, 'password': password})
        self.token = result.pop('token')
        self.user = result
        return self.request('/v1/snapshot')


class RemoteAgenda(AgendaService):
    remote=True
    def __init__(self,db,client,snapshot):
        self.db,self.client,self.data=db,client,snapshot
        self.online=True
        self.pending=None
    def for_form(self):
        form=RemoteAgenda(self.db,self.client,self.data)
        form.online=self.online
        return form
    def condos(self,query=''):
        return [copy.deepcopy(c) for c in self.data['condos'] if query.casefold() in (c['nome']+' '+(c['sindico'] or '')).casefold()]
    def events(self,**filters): return filter_events(self.data['events'],**filters)
    def audit(self): return copy.deepcopy(self.data['audit'])
    def mutate(self,method,*args):
        from app.widgets.network import wait_for
        if not self.online: raise ValueError('Sem conexão. Atualize a agenda antes de salvar.')
        body={'method':method,'args':args,'revision':self.data['revision'],'request_id':str(uuid.uuid4())}
        signature=json.dumps(encode({k:v for k,v in body.items() if k!='request_id'}),sort_keys=True)
        if self.pending and self.pending[0]==signature: body['request_id']=self.pending[1]
        self.pending=(signature,body['request_id'])
        result=wait_for(lambda:self.client.request('/v1/mutate',body))
        self.pending=None
        try: self.data=wait_for(lambda:self.client.request('/v1/snapshot'))
        except ValueError: self.online=False
        return result['result']
    def save_condo(self,values,condo_id=None): return self.mutate('save_condo',values,condo_id)
    def delete_condo(self,condo_id): return self.mutate('delete_condo',condo_id)
    def save_event(self,values,event_id=None): return self.mutate('save_event',values,event_id)
    def set_state(self,event_id,state,result=''): return self.mutate('set_state',event_id,state,result)
    def delete_event(self,event_id): return self.mutate('delete_event',event_id)
