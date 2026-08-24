import io
import os
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="mt_probe_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication, QScrollArea

qt_app = QApplication(sys.argv[:1])

from app.core.logger import setup_logging

setup_logging()

from app.core.engine import LlamaServer
from app.core.glossary import Glossary
from app.core.history import History
from app.ui.main_window import MainWindow
from app.ui.theme import apply_to_application, manager, current_palette

server = LlamaServer()
win = MainWindow(server, Glossary(), History())
manager().changed.connect(apply_to_application)
manager().changed.connect(win.retheme)
apply_to_application()

manager().set_preference("dark")
qt_app.processEvents()
win.tabs.setCurrentIndex(3)
win.show()
qt_app.processEvents()

print("config theme:", __import__("app.core.config", fromlist=["x"]).get("theme"))
print("resolved:", current_palette()["bg"])
print("win.styleSheet() starts:", win.styleSheet()[:60].replace("\n", " "))

scroll = win.tab_settings.findChild(QScrollArea)
vp = scroll.viewport()
print("viewport palette window:", vp.palette().window().color().name())
print("viewport palette base:", vp.palette().base().color().name())
print("viewport autoFillBackground:", vp.autoFillBackground())
holder = scroll.widget()
print("holder palette window:", holder.palette().window().color().name())
print("holder autoFillBackground:", holder.autoFillBackground())
print("holder styleSheet:", repr(holder.styleSheet()[:50]))

out = Path(os.environ["APPDATA"]) / "probe_dark.png"
win.grab().save(str(out))
from collections import Counter

from PySide6.QtGui import QImage

img = QImage(str(out))
c = Counter()
for x in range(40, 110):
    for y in range(60, 80):
        c[img.pixel(x, y)] += 1
print("title region pixels:")
for color, n in c.most_common(5):
    print(hex(color), n)
