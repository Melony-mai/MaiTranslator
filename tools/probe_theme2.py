import io
import os
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="mt_probe2_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QGroupBox, QScrollArea, QWidget

qt_app = QApplication(sys.argv[:1])

from app.core.logger import setup_logging

setup_logging()

from app.core.engine import LlamaServer
from app.core.glossary import Glossary
from app.core.history import History
from app.ui.main_window import MainWindow
from app.ui.theme import apply_to_application, manager

server = LlamaServer()
win = MainWindow(server, Glossary(), History())
manager().changed.connect(apply_to_application)
manager().changed.connect(win.retheme)
apply_to_application()

win.show()
win.tabs.setCurrentIndex(0)
qt_app.processEvents()

manager().set_preference("dark")
qt_app.processEvents()
win.tabs.setCurrentIndex(3)
qt_app.processEvents()

scroll = win.tab_settings.findChild(QScrollArea)
vp = scroll.viewport()
holder = scroll.widget()

from collections import Counter

from PySide6.QtGui import QImage


def sample(tag):
    qt_app.processEvents()
    out = Path(os.environ["APPDATA"]) / f"probe_{tag}.png"
    win.grab().save(str(out))
    img = QImage(str(out))
    c = Counter()
    for x in range(40, 110):
        for y in range(60, 80):
            c[img.pixel(x, y)] += 1
    print(tag, "->", [(hex(k), v) for k, v in c.most_common(3)])


pal = vp.palette()
pal.setColor(QPalette.Window, QColor("#ff0000"))
vp.setPalette(pal)
vp.setAutoFillBackground(True)
sample("vp_red")

holder.setAutoFillBackground(True)
pal2 = holder.palette()
pal2.setColor(QPalette.Window, QColor("#00ff00"))
holder.setPalette(pal2)
sample("holder_green")

gb = win.tab_settings.findChild(QGroupBox)
sample("before_gb")
gb.setAttribute(Qt_WA := __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.WA_StyledBackground, True)
gb.setStyleSheet("background:#0000ff;")
sample("gb_blue")
