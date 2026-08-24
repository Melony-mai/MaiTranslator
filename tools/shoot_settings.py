import io
import os
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="mt_settings_shot_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication, QScrollArea

qt_app = QApplication(sys.argv[:1])

from app.core.logger import setup_logging

setup_logging()

from app.core.engine import LlamaServer
from app.core.glossary import Glossary
from app.core.history import History
from app.ui.main_window import MainWindow

server = LlamaServer()
win = MainWindow(server, Glossary(), History())
win.show()
win.tabs.setCurrentIndex(3)
qt_app.processEvents()

area = win.tab_settings.findChild(QScrollArea)
bar = area.verticalScrollBar()
bar.setValue(bar.maximum())
qt_app.processEvents()
import time

time.sleep(0.3)
qt_app.processEvents()

out = Path(os.environ["APPDATA"]) / "settings_bottom.png"
win.grab().save(str(out))
print("saved", out)
