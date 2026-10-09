import uuid
import time
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from server.api import create_app
from app.utils.wire import encode,decode
from app.utils.clock import now
from app.services.agenda import TYPES

PASSWORD='Senha-de-teste-12345'


def login(c,email='admin@example.com'):
    r=c.post('/v1/login',json={'email':email,'password':PASSWORD});assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}


def snapshot(c,h):return decode(c.get('/v1/snapshot',headers=h).json())

def mutate(c,h,method,args,revision=None,rid=None):
    return c.post('/v1/mutate',headers=h,json=encode({'method':method,'args':args,'revision':revision or snapshot(c,h)['revision'],'request_id':rid or str(uuid.uuid4())}))


def test_two_users_conflicts_receipts_and_access(tmp_path):
    with TestClient(create_app(tmp_path,'admin@example.com',PASSWORD,False)) as c:
        h=login(c);assert c.get('/v1/snapshot').status_code==401
        assert c.post('/v1/users',headers=h,json={'email':'other@example.com','password':PASSWORD}).status_code==200
        other=login(c,'other@example.com')
        assert c.get('/v1/backup',headers=other).status_code==403
        at=now();data={'titulo':'Reunião','tipo':TYPES[0],'inicio':at+timedelta(hours=1),'fim':at+timedelta(hours=2)}
        rev=snapshot(c,h)['revision'];rid=str(uuid.uuid4())
        r=mutate(c,h,'save_event',[data],rev,rid);assert r.status_code==200,r.text
        assert mutate(c,h,'save_event',[data],rev,rid).json()==r.json()
        assert len(snapshot(c,other)['events'])==1
        assert mutate(c,other,'save_event',[data],rev).status_code==409
        eid=r.json()['result'];assert mutate(c,other,'set_state',[eid,'Realizada','Reunião concluída']).status_code==200
        assert snapshot(c,h)['events'][0]['estado']=='Realizada'
        assert mutate(c,h,'pay',[eid,{}]).status_code==400
        user=next(x for x in c.get('/v1/users',headers=h).json() if x['email']=='other@example.com')
        assert c.patch('/v1/users/'+str(user['id']),headers=h,json={'active':False}).status_code==200
        assert c.get('/v1/snapshot',headers=other).status_code==401
        rev=snapshot(c,h)['revision']
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=[pool.submit(mutate,c,h,'save_condo',[{'nome':name}],rev) for name in ('A','B')]
            assert sorted(f.result().status_code for f in results)==[200,409]


def test_online_backup_import_persistence_and_scheduler(tmp_path):
    source=tmp_path/'source';target=tmp_path/'target'
    with TestClient(create_app(source,'admin@example.com',PASSWORD,True)) as c:
        h=login(c);assert mutate(c,h,'save_condo',[{'nome':'Aurora'}]).status_code==200
        backup=c.get('/v1/backup',headers=h).content
        assert backup.startswith(b'SQLite format 3')
        for _ in range(100):
            if list((source/'backups').glob('*.sqlite3')):break
            time.sleep(.01)
        assert list((source/'backups').glob('*.sqlite3'))
    for round in range(2):
        with TestClient(create_app(target,'admin@example.com',PASSWORD,False)) as c:
            h=login(c)
            if round==0:
                assert c.post('/v1/import',headers=h,content=b'invalid').status_code==400
                r=c.post('/v1/import',headers=h,content=backup);assert r.status_code==200,r.text
            assert snapshot(c,h)['condos'][0]['nome']=='Aurora'
            assert c.post('/v1/import',headers=h,content=backup).status_code==409
