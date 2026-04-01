import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QWidget, QDockWidget, QApplication

from .compat import exec_app
from . import resources_rc


FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "dock.ui")
)


class Widget(QWidget, FORM_CLASS):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setupUi(self)

    def update_startpoint(self, point, z=90):
        self.lineEdit_vertexX0.setText(str(point.x()))
        self.lineEdit_vertexY0.setText(str(point.y()))
        self.lineEdit_vertexZ0.setText(str(z))


class Dock(QDockWidget):
    closed = pyqtSignal()

    def __init__(self, parent):
        QDockWidget.__init__(self, parent)
        self.setWidget(Widget(self))
        self.setWindowTitle("Bearing and distance")

    # rwg
    # def keyPressEvent(self, event):
    #     # Return key is on main keyboard, Enter key typically on numberpad
    #     if event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return:
    #         # pprint(event.__dir__())
    #         # print(event.text())
    #         self.focusNextChild()

    def closeEvent(self, event):
        self.closed.emit()


if __name__ == "__main__":
    import sys, os

    app = QApplication(sys.argv)
    c = Dock(None)
    c.show()
    sys.exit(exec_app(app))
