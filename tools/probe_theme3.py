import io
import os
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="mt_probe3_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QImage
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget
from collections import Counter

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
apply_to_application()

win.show()
qt_app.processEvents()

manager().set_preference("dark")
for _ in range(6):
    qt_app.processEvents()
    import time

    time.sleep(0.05)

win.tabs.setCurrentIndex(3)
for _ in range(6):
    qt_app.processEvents()
    time.sleep(0.05)

scroll = win.tab_settings.findChild(QScrollArea)
vp = scroll.viewport()
holder = scroll.widget()


def sample(tag):
    out = Path(os.environ["APPDATA"]) / f"p3_{tag}.png"
    win.grab().save(str(out))
    img = QImage(str(out))
    c = Counter()
    for x in range(40, 110):
        for y in range(60, 80):
            c[img.pixel(x, y)] += 1
    print(tag, "->", [(hex(k), v) for k, v in c.most_common(3)])


sample("baseline")

import time

win.tabs.setCurrentIndex(1)
for _ in range(6):
    qt_app.processEvents()
    time.sleep(0.05)
win.grab()
win.tabs.setCurrentIndex(2)
for _ in range(6):
    qt_app.processEvents()
    time.sleep(0.05)
win.grab()
win.tabs.setCurrentIndex(3)
for _ in range(6):
    qt_app.processEvents()
    time.sleep(0.05)
sample("after_tab12_grabs")

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

holder.setStyleSheet("background:#0000ff;")
holder.setAttribute(Qt.WA_StyledBackground, True)
sample("holder_blue_qss")

vp.setStyleSheet("background:#ff00ff;")
sample("vp_magenta_qss")
