import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from app.database.connection import Database
from app.services.agenda import AgendaService

@pytest.fixture
def service(tmp_path):
    db=Database(tmp_path/'agenda.sqlite3')
    yield AgendaService(db)
    db.engine.dispose()

@pytest.fixture(scope='session')
def qapp():
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance() or QApplication([])
    yield app
    import shiboken6,gc
    for w in app.topLevelWidgets():
        if shiboken6.isValid(w):shiboken6.delete(w)
    app.processEvents();gc.collect()
