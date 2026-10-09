import hashlib
import json
from datetime import timedelta
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QSystemTrayIcon, QApplication
from app.utils.clock import now


def due_reminders(events, seen, at):
    """One reminder per event/time/stage; no alerts for finished or cancelled events."""
    result=[]
    for event in events:
        if event['estado']!='Agendada' or event['fim']<=at: continue
        prefix=f"{event['id']}:{event['inicio'].isoformat()}:"
        minutes=(event['inicio']-at).total_seconds()/60
        if not event['lembrete_hora']: continue
        stage='inicio' if -15<=minutes<=0 else '15min' if 0<minutes<=15 else '1h' if 15<minutes<=60 else None
        if stage and prefix+stage not in seen:
            # Entering a later stage also consumes earlier stages to avoid stale reminders.
            keys=[prefix+s for s in ('1h','15min','inicio')[:{'1h':1,'15min':2,'inicio':3}[stage]]]
            result.append((event,stage,keys))
    return result


class NotificationService(QObject):
    changed=Signal()
    failed=Signal(str)
    def __init__(self,service,backup,tray,parent=None):
        super().__init__(parent)
        self.service,self.db,self.backup,self.tray=service,service.db,backup,tray
        scope=service.client.url+service.client.user['email'] if service.remote else 'local'
        self.prefix='notify:'+hashlib.sha256(scope.encode()).hexdigest()[:16]+':'
        self.timer=QTimer(self);self.timer.timeout.connect(self.check);self.timer.start(30_000)
    def check(self):
        if QApplication.instance().property('network_busy'): return
        try:
            at=now()
            if not self.service.remote: self.backup.automatic(at.date())
            if self.service.remote and not self.service.online: return
            self.changed.emit()
            if self.db.get_setting('notificacoes','1')!='1': return
            if not self.tray.isVisible() or not QSystemTrayIcon.supportsMessages(): return
            events=self.service.events()
            seen=json.loads(self.db.get_setting(self.prefix+'seen','{}'))
            seen={k:v for k,v in seen.items() if v >= (at-timedelta(days=60)).date().isoformat()}
            reminders=due_reminders(events,seen,at)
            alerts=self.service.events(alerts=True)
            daily=bool(alerts) and self.db.get_setting(self.prefix+'day')!=at.date().isoformat()
            if not daily and not reminders: return
            if reminders:
                first,stage,keys=reminders[0]
                when={'1h':'em até 1 hora','15min':'em até 15 minutos','inicio':'começou agora'}[stage]
                message=f"{first['titulo']} — {first['condominio']}\n{first['inicio']:%d/%m às %H:%M} • {when}."
                if len(reminders)>1: message+=f'\nMais {len(reminders)-1} evento(s) com lembrete.'
                if daily: message+=f'\n{len(alerts)} compromisso(s) na central de alertas.'
            else:
                today=sum(e['inicio'].date()<=at.date()<=e['fim'].date() for e in alerts)
                message=f'{len(alerts)} compromisso(s) no período de aviso, sendo {today} hoje. Clique para consultar.'
            self.tray.showMessage('AgendaCondominial',message,QSystemTrayIcon.MessageIcon.Information,12000)
            if daily: self.db.set_setting(self.prefix+'day',at.date().isoformat())
            for event,stage,keys in reminders:
                for key in keys: seen[key]=at.date().isoformat()
            self.db.set_setting(self.prefix+'seen',json.dumps(seen))
        except Exception as exc:
            self.failed.emit(str(exc))
