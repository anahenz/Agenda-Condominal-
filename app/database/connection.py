import os
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.models.entities import Base, Configuracao
SCHEMA_VERSION = 'agenda-1'


def data_dir():
    path = Path(os.getenv('AGENDA_DATA_DIR') or Path(os.getenv('LOCALAPPDATA', Path.home()/'.local/share'))/'AgendaCondominial')
    path.mkdir(parents=True, exist_ok=True)
    return path


class Database:
    def __init__(self, path=None):
        self.path = Path(path) if path else data_dir()/'agenda.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connect()
        Base.metadata.create_all(self.engine)
        with self.session() as s:
            version = s.get(Configuracao,'schema_version')
            if version and version.valor != SCHEMA_VERSION:
                raise ValueError('Banco incompatível com a AgendaCondominial.')
            if not version:
                s.add(Configuracao(chave='schema_version',valor=SCHEMA_VERSION))

    def connect(self):
        self.engine = create_engine('sqlite:///'+str(self.path),connect_args={'timeout':30})
        @event.listens_for(self.engine,'connect')
        def pragmas(c,r):
            c.execute('PRAGMA foreign_keys=ON')
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('PRAGMA busy_timeout=30000')
        self.factory=sessionmaker(bind=self.engine,expire_on_commit=False)

    @contextmanager
    def session(self):
        with self.factory() as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    def get_setting(self,key,default=''):
        with self.session() as s:
            row=s.get(Configuracao,key)
            return row.valor if row else default

    def set_setting(self,key,value):
        with self.session() as s:
            row=s.get(Configuracao,key)
            if row: row.valor=str(value)
            else: s.add(Configuracao(chave=key,valor=str(value)))
