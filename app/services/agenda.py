import copy
import json
from datetime import datetime
from urllib.parse import urlsplit
from sqlalchemy import select
from app.models.entities import Condominio, Evento, Auditoria
from app.utils.clock import now

TYPES=['Assembleia ordinária','Assembleia extraordinária','Reunião de conselho','Reunião com síndico','Reunião interna','Vistoria','Visita técnica','Outro']
STATES=['Todas','Agendada','Próxima','Hoje','Em andamento','Aguardando conclusão','Realizada','Cancelada']
CONDO_FIELDS=set(Condominio.__table__.columns.keys())-{'id'}
EVENT_FIELDS=set(Evento.__table__.columns.keys())-{'id','estado'}


def record(obj):
    return {c.name:getattr(obj,c.name) for c in obj.__table__.columns}


def decorate(row, at=None):
    at=at or now()
    row=copy.deepcopy(row)
    days=(row['inicio'].date()-at.date()).days
    if row['estado'] in ('Cancelada','Realizada'): status=row['estado']
    elif at >= row['fim']: status='Aguardando conclusão'
    elif at >= row['inicio']: status='Em andamento'
    elif days==0: status='Hoje'
    elif days<=row['aviso_dias']: status='Próxima'
    else: status='Agendada'
    row.update(status=status,dias=days)
    return row


def filter_events(rows, query='', status='Todas', condo_id=None, kind='Todos', day=None, history=False, alerts=False, at=None):
    at=at or now(); result=[]
    for original in rows:
        e=decorate(original,at)
        if query.casefold() not in ' '.join(str(e.get(k) or '') for k in ('titulo','condominio','tipo','responsavel','participantes','local','pauta')).casefold(): continue
        if status!='Todas' and e['status']!=status: continue
        if condo_id and e['condominio_id']!=condo_id: continue
        if kind!='Todos' and e['tipo']!=kind: continue
        if day and not e['inicio'].date()<=day<=e['fim'].date(): continue
        if history and e['status'] not in ('Realizada','Cancelada','Aguardando conclusão'): continue
        if alerts and (e['estado']!='Agendada' or e['fim']<=at or e['dias']>e['aviso_dias']): continue
        result.append(e)
    return result


class AgendaService:
    remote=False
    def __init__(self,db): self.db=db
    def condos(self,query=''):
        with self.db.session() as s:
            return [record(c) for c in s.scalars(select(Condominio).order_by(Condominio.nome)) if query.casefold() in (c.nome+' '+(c.sindico or '')).casefold()]
    def events(self,**filters):
        with self.db.session() as s:
            rows=[record(e)|{'condominio':name or 'Administradora'} for e,name in s.execute(select(Evento,Condominio.nome).outerjoin(Condominio).order_by(Evento.inicio))]
        return filter_events(rows,**filters)
    def event(self,event_id): return next((e for e in self.events() if e['id']==event_id),None)
    def save_condo(self,values,condo_id=None):
        if set(values)-CONDO_FIELDS: raise ValueError('Campo de condomínio inválido.')
        if not str(values.get('nome','')).strip(): raise ValueError('Informe o nome do condomínio.')
        if any(not isinstance(v,str) or len(v)>10000 for v in values.values()): raise ValueError('Texto inválido ou muito longo.')
        with self.db.session() as s:
            obj=s.get(Condominio,condo_id) if condo_id else Condominio()
            if obj is None: raise ValueError('Condomínio não encontrado.')
            for key,value in values.items(): setattr(obj,key,value.strip())
            s.add(obj);s.flush()
            s.add(Auditoria(acao='Salvar condomínio',detalhes=f'{obj.id}: {obj.nome}'))
            return obj.id
    def delete_condo(self,condo_id):
        with self.db.session() as s:
            if s.scalar(select(Evento.id).where(Evento.condominio_id==condo_id).limit(1)):
                raise ValueError('Este condomínio possui eventos. Preserve o cadastro para manter o histórico.')
            obj=s.get(Condominio,condo_id)
            if not obj: raise ValueError('Condomínio não encontrado.')
            s.add(Auditoria(acao='Excluir condomínio',detalhes=obj.nome));s.delete(obj)
    def save_event(self,values,event_id=None):
        if set(values)-EVENT_FIELDS: raise ValueError('Campo de evento inválido.')
        for key in ('titulo','tipo','inicio','fim'):
            if not values.get(key): raise ValueError('Preencha título, tipo, início e término.')
        if not isinstance(values['titulo'],str) or not values['titulo'].strip(): raise ValueError('Informe o título.')
        if values['tipo'] not in TYPES: raise ValueError('Tipo de evento inválido.')
        for key in ('inicio','fim'):
            if type(values[key]) is not datetime or values[key].tzinfo is not None: raise ValueError('Use data e horário de Brasília.')
        if values['fim']<=values['inicio']: raise ValueError('O término deve ser depois do início.')
        if (values['fim']-values['inicio']).total_seconds()>31*86400: raise ValueError('Um evento pode durar no máximo 31 dias.')
        days=values.get('aviso_dias',7)
        if type(days) is not int or not 0<=days<=30: raise ValueError('Antecedência deve ser de 0 a 30 dias.')
        if 'lembrete_hora' in values and type(values['lembrete_hora']) is not bool: raise ValueError('Lembrete inválido.')
        for key,value in values.items():
            if isinstance(value,str) and len(value)>10000: raise ValueError('Texto muito longo.')
        link=values.get('link','').strip()
        if link:
            url=urlsplit(link)
            if url.scheme!='https' or not url.hostname or url.username or url.password: raise ValueError('O link deve começar com https:// e não conter senha.')
        cid=values.get('condominio_id')
        if cid is not None and (type(cid) is not int or cid<=0): raise ValueError('Condomínio inválido.')
        with self.db.session() as s:
            if cid and not s.get(Condominio,cid): raise ValueError('Condomínio não encontrado.')
            obj=s.get(Evento,event_id) if event_id else Evento()
            if obj is None: raise ValueError('Evento não encontrado.')
            for key,value in values.items(): setattr(obj,key,value.strip() if isinstance(value,str) else value)
            s.add(obj);s.flush()
            s.add(Auditoria(acao='Editar evento' if event_id else 'Criar evento',detalhes=f'{obj.id}: {obj.titulo} | {obj.inicio}'))
            return obj.id
    def set_state(self,event_id,state,result=''):
        if state not in ('Agendada','Realizada','Cancelada'): raise ValueError('Situação inválida.')
        if not isinstance(result,str) or len(result)>10000: raise ValueError('Resultado inválido.')
        with self.db.session() as s:
            obj=s.get(Evento,event_id)
            if not obj: raise ValueError('Evento não encontrado.')
            obj.estado=state
            if result: obj.resultado=result
            s.add(Auditoria(acao=state,detalhes=f'Evento #{event_id}: {result}'))
    def delete_event(self,event_id):
        with self.db.session() as s:
            obj=s.get(Evento,event_id)
            if not obj: raise ValueError('Evento não encontrado.')
            s.add(Auditoria(acao='Excluir evento',detalhes=json.dumps(record(obj),default=str,ensure_ascii=False)))
            s.delete(obj)
    def audit(self):
        with self.db.session() as s:
            return [record(a) for a in s.scalars(select(Auditoria).order_by(Auditoria.id.desc()).limit(1000))]
    def snapshot(self):
        return {'events':self.events(),'condos':self.condos(),'audit':self.audit()}
