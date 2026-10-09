from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QDoubleValidator, QPainter, QPen, QPixmap, QIcon
from PySide6.QtWidgets import (
    QTableWidget,
    QAbstractItemView,
    QHeaderView,
    QTableWidgetItem,
    QLineEdit,
    QDateEdit,
    QPushButton,
    QLabel,
    QMessageBox,
)
class DateEdit(QDateEdit):
    def __init__(self, value=None):
        super().__init__()
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd/MM/yyyy")
        self.setDate(
            QDate(value.year, value.month, value.day) if value else QDate.currentDate()
        )

    def value(self):
        return self.date().toPython()


class DataTable(QTableWidget):
    def __init__(self, headers):
        super().__init__(0, len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(44)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setDefaultSectionSize(145)

    def load(self, rows):
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for ri, row in enumerate(rows):
            for ci, value in enumerate(row):
                item = QTableWidgetItem(str(value if value is not None else "—"))
                item.setToolTip(str(value if value is not None else "—"))
                color = {
                    "Realizada": "#15803D",
                    "Cancelada": "#6B7280",
                    "Aguardando conclusão": "#B45309",
                    "Hoje": "#B45309",
                    "Próxima": "#B45309",
                }.get(str(value))
                if color:
                    item.setForeground(QColor(color))
                self.setItem(ri, ci, item)


def button(text, callback=None, primary=False):
    b = QPushButton(text)
    if primary:
        b.setObjectName("primary")
    if callback:
        b.clicked.connect(callback)
    return b


def label(text, name=None):
    l = QLabel(text)
    l.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        l.setObjectName(name)
    return l


def confirm(parent, text="Tem certeza que deseja excluir?"):
    box = QMessageBox(parent)
    box.setWindowTitle("Confirmar ação")
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Question)
    yes = box.addButton("Confirmar", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() == yes


def app_icon():
    from pathlib import Path
    return QIcon(str(Path(__file__).resolve().parents[1] / 'assets' / 'app.ico'))
