from datetime import timedelta
from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QLineEdit, QTextEdit, QComboBox, QDateTimeEdit, QSpinBox, QCheckBox
from app.widgets.form_page import FormPage, begin_form, section, field, finish_form
from app.widgets.common import label
from app.services.agenda import TYPES
from app.utils.clock import now


class EventForm(FormPage):
    def __init__(self,service,event=None,duplicate=False):
        super().__init__()
        self.service=service.for_form() if service.remote else service
        self.original=event or {}
        self.event_id=None if duplicate else self.original.get('id')
        outer,body=begin_form(self,'Novo compromisso' if not self.event_id else 'Editar compromisso','Horários de Brasília • os avisos aparecem no aplicativo e nas notificações do Windows.')
        identity=section(body,'Compromisso')
        schedule=section(body,'Data, horário e local')
        details=section(body,'Organização e lembretes')
        self.fields={}
        self.fields['titulo']=QLineEdit(self.original.get('titulo',''))
        self.fields['titulo'].setPlaceholderText('Ex.: Assembleia ordinária — aprovação de contas')
        self.fields['tipo']=QComboBox();self.fields['tipo'].addItems(TYPES)
        self.fields['tipo'].setCurrentText(self.original.get('tipo',TYPES[0]))
        self.fields['condominio_id']=QComboBox();self.fields['condominio_id'].addItem('Administradora / sem condomínio',None)
        for c in service.condos(): self.fields['condominio_id'].addItem(c['nome'],c['id'])
        idx=self.fields['condominio_id'].findData(self.original.get('condominio_id'))
        self.fields['condominio_id'].setCurrentIndex(max(idx,0))
        self.fields['responsavel']=QLineEdit(self.original.get('responsavel',''))
        for i,(key,title) in enumerate([('titulo','Título *'),('tipo','Tipo *'),('condominio_id','Condomínio'),('responsavel','Responsável')]): field(identity,title,self.fields[key],i//2,i%2)
        for i,(key,title,default) in enumerate([('inicio','Início *',now().replace(second=0,microsecond=0)+timedelta(hours=1)),('fim','Término previsto *',now().replace(second=0,microsecond=0)+timedelta(hours=2))]):
            edit=QDateTimeEdit();edit.setCalendarPopup(True);edit.setDisplayFormat('dd/MM/yyyy HH:mm')
            edit.setDateTime(QDateTime(self.original.get(key,default)));self.fields[key]=edit
            field(schedule,title,edit,0,i)
        for i,(key,title) in enumerate([('local','Local / sala'),('link','Link da reunião (HTTPS)')]):
            self.fields[key]=QLineEdit(self.original.get(key,''));field(schedule,title,self.fields[key],1,i)
        for i,(key,title) in enumerate([('participantes','Participantes / convidados'),('pauta','Pauta'),('observacoes','Observações'),('resultado','Registro / resultado da reunião')]):
            edit=QTextEdit();edit.setPlainText(self.original.get(key,''));edit.setFixedHeight(85);self.fields[key]=edit
            field(details,title,edit,i//2,i%2)
        days=QSpinBox();days.setRange(0,30);days.setSuffix(' dia(s) antes');days.setValue(self.original.get('aviso_dias',7));self.fields['aviso_dias']=days
        remind=QCheckBox('Avisar 1 hora antes, 15 minutos antes e no início');remind.setChecked(self.original.get('lembrete_hora',True));self.fields['lembrete_hora']=remind
        field(details,'Incluir no resumo diário a partir de',days,2,0)
        field(details,'Lembretes de horário',remind,2,1)
        body.addStretch();finish_form(self,outer,'Salvar compromisso',self.save)
    def watch_changes(self):
        super().watch_changes()
        for key in ('inicio','fim'): self.fields[key].dateTimeChanged.connect(lambda *_:setattr(self,'dirty',True))
        self.fields['aviso_dias'].valueChanged.connect(lambda *_:setattr(self,'dirty',True))
        self.fields['lembrete_hora'].toggled.connect(lambda *_:setattr(self,'dirty',True))
    def save(self):
        try:
            data={}
            for key,e in self.fields.items():
                if isinstance(e,QDateTimeEdit): value=e.dateTime().toPython().replace(tzinfo=None)
                elif isinstance(e,QCheckBox): value=e.isChecked()
                elif isinstance(e,QSpinBox): value=e.value()
                elif isinstance(e,QTextEdit): value=e.toPlainText().strip()
                elif isinstance(e,QComboBox): value=e.currentData() if key=='condominio_id' else e.currentText()
                else: value=e.text().strip()
                data[key]=value
            self.saved_id=self.service.save_event(data,self.event_id);self.accept()
        except Exception as exc: self.show_error(str(exc))


class CondoForm(FormPage):
    def __init__(self,service,condo=None):
        super().__init__();self.service=service.for_form() if service.remote else service;self.original=condo or {};self.fields={}
        outer,body=begin_form(self,'Editar condomínio' if condo else 'Novo condomínio','Cadastre os locais vinculados às assembleias e reuniões.')
        grid=section(body,'Dados do condomínio')
        for i,(key,title) in enumerate([('nome','Nome *'),('cnpj','CNPJ'),('endereco','Endereço'),('cidade','Cidade'),('sindico','Síndico'),('telefone','Telefone'),('email','E-mail'),('observacoes','Observações')]):
            edit=QLineEdit(self.original.get(key,''))
            if key=='cnpj': edit.setInputMask('00.000.000/0000-00;_')
            self.fields[key]=edit;field(grid,title,edit,i//2,i%2)
        body.addStretch();finish_form(self,outer,'Salvar condomínio',self.save)
    def save(self):
        try:
            values={key:e.text().strip() for key,e in self.fields.items()}
            digits=''.join(c for c in values['cnpj'] if c.isdigit())
            if digits and len(digits)!=14: raise ValueError('Complete o CNPJ ou deixe vazio.')
            if not digits: values['cnpj']=''
            self.saved_id=self.service.save_condo(values,self.original.get('id'));self.accept()
        except Exception as exc:self.show_error(str(exc))


class Details(FormPage):
    def __init__(self,event):
        super().__init__();outer,body=begin_form(self,event['titulo'],event['condominio']+' • '+event['tipo'])
        grid=section(body,'Detalhes do compromisso')
        items=[('Situação',event['status']),('Responsável',event['responsavel']),('Início',event['inicio'].strftime('%d/%m/%Y %H:%M')),('Término',event['fim'].strftime('%d/%m/%Y %H:%M')),('Local',event['local']),('Link',event['link']),('Participantes',event['participantes']),('Pauta',event['pauta']),('Observações',event['observacoes']),('Resultado',event['resultado'])]
        for i,(title,text) in enumerate(items):
            text=label(text or '—');text.setWordWrap(True);field(grid,title,text,i//2,i%2)
        body.addStretch()


class CompleteForm(FormPage):
    def __init__(self,service,event):
        super().__init__();self.service=service.for_form() if service.remote else service;self.event=event
        outer,body=begin_form(self,'Registrar realização',event['titulo'])
        grid=section(body,'Registro da reunião')
        self.notes=QTextEdit();self.notes.setPlainText(event['resultado']);field(grid,'Resultado / observações',self.notes,0,0,2)
        body.addStretch();finish_form(self,outer,'Marcar como realizada',self.save)
    def save(self):
        try:self.service.set_state(self.event['id'],'Realizada',self.notes.toPlainText());self.accept()
        except Exception as exc:self.show_error(str(exc))
