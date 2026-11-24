from AnyQt.QtCore import Qt
from AnyQt.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from AnyQt.QtWidgets import QApplication
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT


class SnapshotNavigationToolbar(NavigationToolbar2QT):
    def __init__(self, canvas, parent=None):
        super().__init__(canvas, parent)
        self._add_copy_action()

    def _add_copy_action(self):
        self.addSeparator()
        action = self.addAction(self._copy_icon(), "Copy", self.copy_canvas_to_clipboard)
        action.setToolTip("Copy plot snapshot to clipboard")
        action.setStatusTip("Copy plot snapshot to clipboard")

    def copy_canvas_to_clipboard(self):
        self.canvas.draw()
        QApplication.clipboard().setPixmap(self.canvas.grab())

    @staticmethod
    def _copy_icon():
        icon = QIcon.fromTheme("edit-copy")
        if not icon.isNull():
            return icon

        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(80, 80, 80), 1.4))
        painter.drawRoundedRect(6, 3, 8, 10, 1.5, 1.5)
        painter.drawRoundedRect(3, 6, 8, 10, 1.5, 1.5)
        painter.end()

        return QIcon(pixmap)
