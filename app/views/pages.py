from datetime import timedelta
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QFrame,QLineEdit,QComboBox,QMenu,QCalendarWidget,QMessageBox,QHeaderView
from app.widgets.common import label,button,DataTable,confirm
from app.views.forms import EventForm,CondoForm,Details,CompleteForm
from app.services.agenda import TYPES,STATES
from app.utils.clock import now


class EventTable(DataTable):
    def __init__(self,window):
        super().__init__(['Condomínio','Compromisso','Tipo','Data e hora','Local','Responsável','Situação','Ações'])
        self.window_ref=window;self.events=[]
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(7,QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(3,165);self.setColumnWidth(7,66)
        self.cellDoubleClicked.connect(lambda r,c:self.action('Visualizar',self.events[r]))
    def display(self,events):
        self.events=events
        self.load([[e['condominio'],e['titulo'],e['tipo'],e['inicio'].strftime('%d/%m/%Y %H:%M'),e['local'],e['responsavel'],e['status'],''] for e in events])
        for i,e in enumerate(events):
            b=button('⋯');b.setAccessibleName('Ações de '+e['titulo']);b.clicked.connect(lambda checked=False,event=e,btn=b:self.menu(event,btn));self.setCellWidget(i,7,b)
    def menu(self,e,b):
        menu=QMenu(self)
        for name in ['Visualizar','Editar','Duplicar','Marcar como realizada','Cancelar evento','Reabrir evento','Excluir']:
            act=menu.addAction(name);act.triggered.connect(lambda checked=False,n=name:self.action(n,e))
        menu.exec(b.mapToGlobal(b.rect().bottomLeft()))
    def action(self,name,e):
        w=self.window_ref
        try:
            if name=='Visualizar':w.open_form(Details(e))
            elif name=='Editar':w.open_form(EventForm(w.service,e))
            elif name=='Duplicar':w.open_form(EventForm(w.service,e,True))
            elif name=='Marcar como realizada':w.open_form(CompleteForm(w.service,e))
            elif name=='Excluir' and confirm(w,'Tem certeza que deseja excluir este evento? O registro da exclusão permanece na auditoria.'):
                w.service.delete_event(e['id']);w.changed()
            elif name in ('Cancelar evento','Reabrir evento') and confirm(w,name+'?'):
                w.service.set_state(e['id'],'Cancelada' if name=='Cancelar evento' else 'Agendada');w.changed()
        except Exception as exc:QMessageBox.warning(w,'Não foi possível concluir',str(exc))


class Dashboard(QWidget):
    def __init__(self,w):
        super().__init__();self.w=w;layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(18)
        row=QHBoxLayout();row.addWidget(label('Visão geral','heading'));row.addStretch();row.addWidget(button('Novo compromisso',lambda:w.open_form(EventForm(w.service)),True));layout.addLayout(row)
        layout.addWidget(label('Assembleias, reuniões e compromissos em um só lugar.','muted'))
        cards=QGridLayout();self.values=[]
        for i,title in enumerate(['Hoje','Próximos 7 dias','Agendados','Aguardando conclusão','Realizados no mês','Condomínios']):
            frame=QFrame();frame.setObjectName('card');content=QVBoxLayout(frame);content.setContentsMargins(18,14,18,14)
            content.addWidget(label(title,'muted'));value=label('0','heading');content.addWidget(value);self.values.append(value);cards.addWidget(frame,i//3,i%3)
        layout.addLayout(cards);layout.addWidget(label('Próximos compromissos','sectionTitle'));self.table=EventTable(w);layout.addWidget(self.table,1)
        self.empty=label('Cadastre o primeiro compromisso para acompanhar os lembretes.','muted');layout.addWidget(self.empty)
    def refresh(self):
        rows=self.w.service.events();at=now();active=[e for e in rows if e['estado']=='Agendada' and e['fim']>at]
        counts=[sum(e['inicio'].date()<=at.date()<=e['fim'].date() for e in active),sum(0<e['dias']<=7 for e in active),len(active),sum(e['status']=='Aguardando conclusão' for e in rows),sum(e['estado']=='Realizada' and (e['inicio'].year,e['inicio'].month)==(at.year,at.month) for e in rows),len(self.w.service.condos())]
        for value,count in zip(self.values,counts):value.setText(str(count))
        self.table.display(active);self.empty.setVisible(not active)


class EventsPage(QWidget):
    def __init__(self,w,history=False,alerts=False):
        super().__init__();self.w=w;self.history=history;self.alerts=alerts
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(16)
        row=QHBoxLayout();row.addWidget(label('Histórico' if history else 'Central de alertas' if alerts else 'Compromissos','heading'));row.addStretch();row.addWidget(button('Novo compromisso',lambda:w.open_form(EventForm(w.service)),True));layout.addLayout(row)
        if alerts:layout.addWidget(label('Eventos no período de aviso configurado, incluindo os de hoje.','muted'))
        row=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Título, condomínio, responsável ou participante');self.search.returnPressed.connect(self.reload);row.addWidget(self.search,1)
        self.state=QComboBox();self.state.addItems(STATES);self.state.currentIndexChanged.connect(self.reload);row.addWidget(self.state)
        self.kind=QComboBox();self.kind.addItems(['Todos']+TYPES);self.kind.currentIndexChanged.connect(self.reload);row.addWidget(self.kind)
        layout.addLayout(row);row=QHBoxLayout();self.condo=QComboBox();self.condo.currentIndexChanged.connect(self.reload);row.addWidget(self.condo,1);row.addWidget(button('Pesquisar',self.reload));layout.addLayout(row)
        self.table=EventTable(w);layout.addWidget(self.table,1);self.count=label('','muted');layout.addWidget(self.count)
    def refresh(self):
        selected=self.condo.currentData();self.condo.blockSignals(True);self.condo.clear();self.condo.addItem('Todos os condomínios',None)
        for c in self.w.service.condos():self.condo.addItem(c['nome'],c['id'])
        self.condo.setCurrentIndex(max(0,self.condo.findData(selected)));self.condo.blockSignals(False);self.reload()
    def reload(self):
        if not hasattr(self,'table'):return
        rows=self.w.service.events(query=self.search.text(),status=self.state.currentText(),kind=self.kind.currentText(),condo_id=self.condo.currentData(),history=self.history,alerts=self.alerts)
        self.table.display(rows);self.count.setText(f'{len(rows)} compromisso(s) encontrado(s)')


class CondoPage(QWidget):
    def __init__(self,w):
        super().__init__();self.w=w;self.rows=[]
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);row=QHBoxLayout();row.addWidget(label('Condomínios','heading'));row.addStretch();row.addWidget(button('Novo condomínio',lambda:w.open_form(CondoForm(w.service)),True));layout.addLayout(row)
        self.search=QLineEdit();self.search.setPlaceholderText('Pesquisar condomínio ou síndico');self.search.textChanged.connect(self.refresh);layout.addWidget(self.search)
        self.table=DataTable(['Nome','Síndico','Telefone','E-mail','Ações']);layout.addWidget(self.table,1)
    def refresh(self):
        self.rows=self.w.service.condos(self.search.text());self.table.load([[c['nome'],c['sindico'],c['telefone'],c['email'],''] for c in self.rows])
        for i,c in enumerate(self.rows):
            b=button('⋯');b.clicked.connect(lambda checked=False,r=c,btn=b:self.menu(r,btn));self.table.setCellWidget(i,4,b)
    def menu(self,c,b):
        menu=QMenu(self);menu.addAction('Editar / visualizar dados').triggered.connect(lambda:self.w.open_form(CondoForm(self.w.service,c)))
        menu.addAction('Ver compromissos').triggered.connect(lambda:self.show_events(c))
        menu.addAction('Excluir').triggered.connect(lambda:self.delete(c));menu.exec(b.mapToGlobal(b.rect().bottomLeft()))
    def show_events(self,c):
        self.w.navigate(1);page=self.w.pages[1];page.condo.setCurrentIndex(page.condo.findData(c['id']))
    def delete(self,c):
        if confirm(self):
            try:self.w.service.delete_condo(c['id']);self.w.changed()
            except Exception as exc:QMessageBox.warning(self,'Não foi possível excluir',str(exc))


class CalendarPage(QWidget):
    def __init__(self,w):
        super().__init__();self.w=w;self.marked=[];layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        layout.addWidget(label('Calendário','heading'));layout.addWidget(label('Datas destacadas têm compromissos. Clique em um dia para consultar.','muted'))
        self.calendar=QCalendarWidget();self.calendar.setMaximumHeight(320);self.calendar.setSelectedDate(QDate(now().date()));self.calendar.selectionChanged.connect(self.reload);self.calendar.currentPageChanged.connect(self.mark_dates)
        layout.addWidget(self.calendar);self.table=EventTable(w);layout.addWidget(self.table,1)
    def mark_dates(self,*args):
        for day in self.marked:self.calendar.setDateTextFormat(day,QTextCharFormat())
        self.marked=[];fmt=QTextCharFormat();fmt.setBackground(QColor('#FCE7E9'));fmt.setForeground(QColor('#991B1B'));fmt.setFontWeight(700)
        for e in self.w.service.events():
            if e['estado']=='Cancelada':continue
            day=e['inicio'].date()
            while day<=e['fim'].date():
                q=QDate(day)
                if q.year()==self.calendar.yearShown() and q.month()==self.calendar.monthShown():self.calendar.setDateTextFormat(q,fmt);self.marked.append(q)
                day+=timedelta(days=1)
    def refresh(self):self.mark_dates();self.reload()
    def reload(self):self.table.display(self.w.service.events(day=self.calendar.selectedDate().toPython()))
