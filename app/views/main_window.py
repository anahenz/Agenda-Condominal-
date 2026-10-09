from PySide6.QtCore import QTimer, QSize
from PySide6.QtWidgets import QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QStackedWidget,QLineEdit,QSystemTrayIcon,QMenu,QApplication
from app.widgets.common import label,button,app_icon,confirm
from app.widgets.icons import line_icon
from app.widgets.network import NetworkJob
from app.services.agenda import AgendaService
from app.services.backup import BackupService
from app.services.notifications import NotificationService
from app.views.pages import Dashboard,EventsPage,CondoPage,CalendarPage
from app.views.settings_pages import SettingsPage,BackupPage
from app.views.online_page import OnlinePage


class MainWindow(QMainWindow):
    def __init__(self,db,service=None):
        super().__init__();self.db=db;self.service=service or AgendaService(db);self.remote=self.service.remote
        self.backup=BackupService(db);self.form_stack=[];self.sync_job=None;self.quitting=False
        self.setWindowTitle('AgendaCondominial | Assembleias e reuniões');self.setWindowIcon(app_icon());self.resize(1400,880);self.setMinimumSize(1080,700)
        root=QWidget();row=QHBoxLayout(root);row.setContentsMargins(0,0,0,0);row.setSpacing(0);self.setCentralWidget(root)
        sidebar=QWidget();sidebar.setObjectName('sidebar');sidebar.setFixedWidth(228);side=QVBoxLayout(sidebar);side.setContentsMargins(16,26,16,20);side.setSpacing(6)
        side.addWidget(label('Agenda','brand'));side.addWidget(label('CONDOMINIAL','subtitle'));side.addSpacing(28);row.addWidget(sidebar)
        body=QWidget();layout=QVBoxLayout(body);layout.setContentsMargins(26,20,26,20);layout.setSpacing(22);row.addWidget(body,1)
        top=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Pesquisar assembleia, reunião, condomínio ou responsável…');self.search.returnPressed.connect(self.global_search);top.addWidget(self.search,1);top.addWidget(button('Pesquisar',self.global_search))
        self.alert=button('Alertas  0',self.open_alerts);self.alert.setIcon(line_icon('bell'));top.addWidget(self.alert)
        if self.remote:top.addWidget(button('Atualizar',self.sync_online))
        layout.addLayout(top);self.stack=QStackedWidget();layout.addWidget(self.stack,1)
        self.pages=[Dashboard(self),EventsPage(self),CondoPage(self),CalendarPage(self),EventsPage(self,history=True),EventsPage(self,alerts=True),SettingsPage(db),OnlinePage(self.service,self.sync_online) if self.remote else BackupPage(db,self.backup,self.changed)]
        self.nav=[]
        names=['Visão geral','Compromissos','Condomínios','Calendário','Histórico','Central de alertas','Configurações','Equipe e backup' if self.remote else 'Backup']
        icons=['dashboard','calendar','building','calendar','history','bell','settings','backup']
        for i,(name,icon,page) in enumerate(zip(names,icons,self.pages)):
            self.stack.addWidget(page);b=button(name);b.setObjectName('nav');b.setCheckable(True);b.setIcon(line_icon(icon));b.setIconSize(QSize(16,16));b.clicked.connect(lambda checked=False,index=i:self.navigate(index));side.addWidget(b);self.nav.append(b)
        side.addStretch();side.addWidget(label('Seus compromissos,\nsempre à vista.','muted'));side.addSpacing(12);side.addWidget(label('Agenda • versão 1.0.0','muted'))
        side.addWidget(button('Sair',self.quit_app))
        self.tray=QSystemTrayIcon(app_icon(),self);self.tray.setToolTip('AgendaCondominial')
        menu=QMenu();menu.addAction('Abrir agenda').triggered.connect(self.bring_to_front);menu.addAction('Central de alertas').triggered.connect(self.open_alerts);menu.addAction('Sair').triggered.connect(self.quit_app);self.tray.setContextMenu(menu);self.tray.messageClicked.connect(self.open_alerts)
        self.tray.activated.connect(lambda reason:self.bring_to_front() if reason in (QSystemTrayIcon.ActivationReason.Trigger,QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        if QSystemTrayIcon.isSystemTrayAvailable():self.tray.show()
        self.notifications=NotificationService(self.service,self.backup,self.tray,self);self.notifications.changed.connect(self.refresh_current);self.notifications.failed.connect(self.background_error)
        self.sync_timer=QTimer(self);self.sync_timer.timeout.connect(self.sync_online)
        if self.remote:self.sync_timer.start(30_000)
        self.startup_timer=QTimer(self);self.startup_timer.setSingleShot(True);self.startup_timer.timeout.connect(self.notifications.check);self.startup_timer.start(800)
        self.navigate(0)
        self.statusBar().showMessage(('Equipe online • '+self.service.client.user['email'] if self.remote else 'Agenda local')+' • Horários de Brasília')
    def navigate(self,index):
        if self.form_stack and any(p.dirty for p in self.form_stack) and not confirm(self,'Descartar as alterações não salvas?'):return
        while self.form_stack:
            page=self.form_stack.pop();self.stack.removeWidget(page);page.deleteLater()
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.nav):b.setChecked(i==index)
        self.refresh_current()
    def open_form(self,page):
        self.previous=self.stack.currentIndex();self.form_stack.append(page);self.stack.addWidget(page);self.stack.setCurrentWidget(page);page.watch_changes();page.completed.connect(lambda result,p=page:self.finish_form(p,result))
    def finish_form(self,page,result):
        if not result and page.dirty and not confirm(self,'Descartar as alterações não salvas?'):return
        self.form_stack.remove(page);self.stack.setCurrentIndex(self.previous);self.stack.removeWidget(page);page.deleteLater()
        if result:self.changed()
        else:self.refresh_current()
    def refresh_current(self):
        try:
            self.stack.currentWidget().refresh();self.alert.setText('Alertas  '+str(len(self.service.events(alerts=True))))
        except Exception as exc:self.background_error(str(exc))
    def changed(self):
        if self.remote:self.sync_online()
        else:self.notifications.check()
        self.refresh_current()
    def global_search(self):
        self.navigate(1)
        if self.form_stack:return
        page=self.pages[1];page.state.setCurrentIndex(0);page.kind.setCurrentIndex(0);page.condo.setCurrentIndex(0);page.search.setText(self.search.text());page.reload()
    def open_alerts(self):self.bring_to_front();self.navigate(5)
    def bring_to_front(self):self.showNormal();self.raise_();self.activateWindow()
    def background_error(self,message):self.statusBar().showMessage('Atenção: '+message)
    def sync_online(self):
        if not self.remote or self.form_stack or self.sync_job is not None or QApplication.instance().property('network_busy'):return
        self.sync_job=NetworkJob(lambda:self.service.client.request('/v1/snapshot'),self);self.sync_job.finished.connect(self.sync_finished);self.sync_job.start()
    def sync_finished(self):
        job=self.sync_job;self.sync_job=None
        if job.error:self.service.online=False;self.background_error('Sem conexão. A agenda pode estar desatualizada. '+str(job.error))
        elif not self.form_stack:
            self.service.data=job.result;self.service.online=True;self.refresh_current();self.statusBar().showMessage('Equipe online • Agenda atualizada • Horários de Brasília');self.notifications.check()
        job.deleteLater()
    def stop(self):
        self.notifications.timer.stop();self.sync_timer.stop();self.startup_timer.stop();self.tray.hide()
        if self.sync_job:self.sync_job.wait()
    def quit_app(self):
        if self.form_stack and any(p.dirty for p in self.form_stack) and not confirm(self,'Sair e descartar alterações não salvas?'):return
        self.quitting=True;self.stop();QApplication.instance().quit()
    def closeEvent(self,event):
        if not self.quitting and self.db.get_setting('fechar_bandeja','1')=='1' and self.tray.isVisible():self.hide();event.ignore()
        elif self.form_stack and not self.quitting and any(p.dirty for p in self.form_stack) and not confirm(self,'Sair e descartar alterações não salvas?'):event.ignore()
        else:self.quitting=True;self.stop();event.accept();QApplication.instance().quit()
