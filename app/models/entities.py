from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import declarative_base
Base = declarative_base()


class Condominio(Base):
    __tablename__ = 'condominios'
    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    cnpj = Column(String(18), default='')
    endereco = Column(String(300), default='')
    cidade = Column(String(100), default='')
    sindico = Column(String(200), default='')
    telefone = Column(String(40), default='')
    email = Column(String(200), default='')
    observacoes = Column(Text, default='')


class Evento(Base):
    __tablename__ = 'eventos'
    __table_args__ = (CheckConstraint('fim > inicio', name='ck_periodo'),)
    id = Column(Integer, primary_key=True)
    condominio_id = Column(Integer, ForeignKey('condominios.id', ondelete='RESTRICT'))
    titulo = Column(String(200), nullable=False)
    tipo = Column(String(100), nullable=False)
    inicio = Column(DateTime, nullable=False, index=True)
    fim = Column(DateTime, nullable=False)
    local = Column(String(300), default='')
    link = Column(String(1000), default='')
    responsavel = Column(String(200), default='')
    participantes = Column(Text, default='')
    pauta = Column(Text, default='')
    observacoes = Column(Text, default='')
    aviso_dias = Column(Integer, nullable=False, default=7)
    lembrete_hora = Column(Boolean, nullable=False, default=True)
    estado = Column(String(30), nullable=False, default='Agendada')
    resultado = Column(Text, default='')


class Configuracao(Base):
    __tablename__ = 'configuracoes'
    chave = Column(String(100), primary_key=True)
    valor = Column(Text, nullable=False)


class Auditoria(Base):
    __tablename__ = 'auditoria'
    id = Column(Integer, primary_key=True)
    data = Column(DateTime, default=datetime.now, nullable=False)
    acao = Column(String(100), nullable=False)
    detalhes = Column(Text, nullable=False)
