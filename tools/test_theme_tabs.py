import io
import os
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="mt_theme2_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

qt_app = QApplication(sys.argv[:1])

from app.core.logger import setup_logging

setup_logging()

from app.core.engine import LlamaServer
from app.core.glossary import Glossary
from app.core.history import History
from app.core.translator import TranslationService
from app.ui.main_window import MainWindow
from app.ui.theme import apply_to_application, manager

server = LlamaServer()
glossary = Glossary()
history = History()
service = TranslationService(server, glossary, history)
win = MainWindow(server, glossary, history)

manager().changed.connect(apply_to_application)
apply_to_application()

history.add("zh", "en", "今天天气真好，我们去公园散步吧。", "The weather is nice today; let's take a walk in the park.", 420.0)
history.add("en", "zh", "Artificial intelligence is changing the world.", "人工智能正在改变世界。", 380.0)
glossary.add("大模型", "LLM")
glossary.add("混元", "Hunyuan")

shots = Path(os.environ["APPDATA"]) / "shots"
shots.mkdir(exist_ok=True)

win.show()
qt_app.processEvents()


def settle(times=6):
    import time

    for _ in range(times):
        qt_app.processEvents()
        time.sleep(0.05)


for pref in ("dark", "light"):
    manager().set_preference(pref)
    settle()
    for tab, name in ((1, "history"), (2, "glossary"), (3, "settings")):
        win.tabs.setCurrentIndex(tab)
        settle()
        win.grab().save(str(shots / f"tab_{name}_{pref}.png"))
    win.activateWindow()
    win.raise_()
    settle(12)
    screen = qt_app.primaryScreen()
    geo = win.frameGeometry()
    screen.grabWindow(0, geo.x(), geo.y(), geo.width(), geo.height()).save(
        str(shots / f"screen_settings_{pref}.png")
    )

print("tab screenshots saved to", shots)
