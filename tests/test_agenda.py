from datetime import datetime,timedelta
import pytest
from app.services.agenda import TYPES,decorate
from app.services.notifications import due_reminders
from app.services.backup import BackupService
from app.utils.clock import now


def values(at=None):
    at=at or now()
    return dict(titulo='Assembleia ordinária',tipo=TYPES[0],inicio=at+timedelta(days=7),fim=at+timedelta(days=7,hours=1),aviso_dias=7,lembrete_hora=True)


def test_crud_history_and_condo(service):
    cid=service.save_condo({'nome':'Residencial Aurora','sindico':'Ana'})
    eid=service.save_event(values()|{'condominio_id':cid})
    assert service.events(query='Ana')==[]
    assert service.events(query='Aurora')[0]['id']==eid
    with pytest.raises(ValueError):service.delete_condo(cid)
    service.set_state(eid,'Realizada','Pauta aprovada')
    assert service.events(history=True)[0]['resultado']=='Pauta aprovada'
    assert service.events(alerts=True)==[]
    service.set_state(eid,'Agendada')
    assert len(service.events(alerts=True))==1
    service.set_state(eid,'Cancelada')
    assert service.events(alerts=True)==[]
    service.delete_event(eid);service.delete_condo(cid)
    assert service.events()==[]
    assert any(a['acao']=='Excluir evento' for a in service.audit())

@pytest.mark.parametrize('delta,expected',[(8,'Agendada'),(7,'Próxima'),(1,'Próxima'),(0,'Hoje'),(-1,'Aguardando conclusão')])
def test_status_boundaries(service,delta,expected):
    at=datetime(2026,10,9,9)
    data=values(at)|{'inicio':at+timedelta(days=delta,hours=1),'fim':at+timedelta(days=delta,hours=2)}
    eid=service.save_event(data)
    assert service.events(at=at)[0]['status']==expected
    assert len(service.events(alerts=True,at=at))==(1 if 0<=delta<=7 else 0)


def test_time_reminders_and_dedup(service):
    at=datetime(2026,10,9,9);eid=service.save_event(values(at)|{'inicio':at+timedelta(hours=1),'fim':at+timedelta(hours=2)})
    rows=service.events(at=at)
    first=due_reminders(rows,{},at);assert first[0][1]=='1h'
    seen={k:1 for k in first[0][2]}
    assert due_reminders(rows,seen,at+timedelta(minutes=1))==[]
    next=due_reminders(rows,seen,at+timedelta(minutes=45));assert next[0][1]=='15min'
    seen.update({k:1 for k in next[0][2]})
    start=due_reminders(rows,seen,at+timedelta(hours=1));assert start[0][1]=='inicio'
    seen.update({k:1 for k in start[0][2]})
    assert due_reminders(rows,seen,at+timedelta(hours=1,minutes=1))==[]
    assert due_reminders(rows,{},at+timedelta(hours=2))==[]
    service.set_state(eid,'Cancelada');assert due_reminders(service.events(),{},at)==[]


def test_validation_and_backup(service,tmp_path):
    with pytest.raises(ValueError):service.save_event(values()|{'fim':now()-timedelta(days=1)})
    with pytest.raises(ValueError):service.save_event(values()|{'link':'javascript:alert(1)'})
    with pytest.raises(ValueError):service.save_event(values()|{'aviso_dias':-1})
    with pytest.raises(ValueError):service.save_event(values()|{'estado':'Realizada'})
    service.save_event(values());backup=BackupService(service.db);path=backup.create(tmp_path/'backup')
    service.save_event(values()|{'titulo':'Outro'})
    backup.restore(path);assert len(service.events())==1


def test_embedded_forms(qapp,service):
    from app.views.main_window import MainWindow
    from app.views.forms import EventForm,CondoForm
    from app.utils.theme import apply_light_theme,load_stylesheet
    import shiboken6
    apply_light_theme(qapp);qapp.setStyleSheet(load_stylesheet())
    w=MainWindow(service.db);w.startup_timer.stop();w.notifications.timer.stop()
    form=CondoForm(w.service);w.open_form(form);form.fields['nome'].setText('Aurora');form.save()
    assert service.condos()[0]['nome']=='Aurora'
    event=EventForm(w.service);w.open_form(event);event.fields['titulo'].setText('Reunião do conselho');event.save()
    assert service.events()[0]['titulo']=='Reunião do conselho'
    assert w.form_stack==[]
    w.navigate(3);assert w.pages[3].marked
    assert all('Pagar' not in b.text() for b in w.nav)
    w.quitting=True;w.close();shiboken6.delete(w)


def test_notification_summary_grouping_and_persisted_dedup(qapp,service,monkeypatch):
    import app.services.notifications as module
    at=datetime(2026,10,9,9)
    monkeypatch.setattr(module,'now',lambda:at)
    monkeypatch.setattr(module.QSystemTrayIcon,'supportsMessages',staticmethod(lambda:True))
    for title in ('Reunião A','Reunião B'):
        service.save_event(values(at)|{'titulo':title,'inicio':at+timedelta(hours=1),'fim':at+timedelta(hours=2)})
    class Tray:
        def __init__(self):self.messages=[]
        def isVisible(self):return True
        def showMessage(self,*args):self.messages.append(args)
    tray=Tray();notifier=module.NotificationService(service,BackupService(service.db),tray);notifier.timer.stop()
    notifier.check();assert len(tray.messages)==1
    assert 'Mais 1' in tray.messages[0][1]
    notifier.check();assert len(tray.messages)==1
    # Reopening the client does not repeat a stage or the day's summary.
    reopened=module.NotificationService(service,BackupService(service.db),tray);reopened.timer.stop();reopened.check()
    assert len(tray.messages)==1
    at+=timedelta(minutes=45);reopened.check();assert len(tray.messages)==2
    for e in service.events():service.set_state(e['id'],'Realizada')
    at+=timedelta(minutes=15);reopened.check();assert len(tray.messages)==2


def test_reject_financial_backup(service,tmp_path):
    import sqlite3
    path=tmp_path/'wrong.sqlite3'
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT)')
        c.execute("INSERT INTO configuracoes VALUES ('schema_version','1')")
    with pytest.raises(ValueError):BackupService(service.db).validate(path)
