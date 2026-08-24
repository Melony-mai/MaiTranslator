import io
import os
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="mt_theme_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

qt_app = QApplication(sys.argv[:1])

from app.core.logger import setup_logging

setup_logging()

from app.ui.theme import (
    LIGHT,
    DARK,
    app_stylesheet,
    floating_stylesheet,
    current_palette,
    manager,
)

for name, pal in (("light", LIGHT), ("dark", DARK)):
    s1 = app_stylesheet(pal)
    s2 = floating_stylesheet(pal)
    for tok in ["$bg", "$text", "$accent", "$border", "$card", "$selection_bg"]:
        assert tok not in s1, f"unreplaced {tok} in app qss ({name})"
        assert tok not in s2, f"unreplaced {tok} in floating qss ({name})"
print("stylesheets render without unreplaced tokens")

from app.core.engine import LlamaServer
from app.core.glossary import Glossary
from app.core.history import History
from app.core.translator import TranslationService
from app.controller import AppController
from app.ui.main_window import MainWindow

server = LlamaServer()
glossary = Glossary()
history = History()
service = TranslationService(server, glossary, history)
controller = AppController(service, server)
win = MainWindow(server, glossary, history)

from app.ui.theme import apply_to_application

manager().changed.connect(apply_to_application)
manager().changed.connect(controller.floating.retheme)
apply_to_application()

shots = Path(os.environ["APPDATA"]) / "shots"
shots.mkdir(exist_ok=True)


def capture(tag):
    win.show()
    qt_app.processEvents()
    win.grab().save(str(shots / f"main_{tag}.png"))
    fw = controller.floating
    fw.begin_translation("The weather is nice today.", "英 → 中")
    fw.set_result("今天天气真好。", 420.0, "已自动复制")
    qt_app.processEvents()
    fw.grab().save(str(shots / f"float_{tag}.png"))
    fw.close()


for pref in ("dark", "light"):
    manager().set_preference(pref)
    qt_app.processEvents()
    assert current_palette() is (DARK if pref == "dark" else LIGHT)
    assert win.styleSheet() == app_stylesheet(current_palette()), "main window stylesheet not updated"
    capture(pref)

manager().set_preference("dark")
qt_app.processEvents()
capture("dark_again")
assert current_palette() is DARK

print("theme switching works live; screenshots at", shots)
print("ALL THEME TESTS PASSED")
