import io
import os
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="mt_restore_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

qt_app = QApplication(sys.argv[:1])

from app.core.logger import setup_logging

setup_logging()

from app.core import config
from app.core.engine import LlamaServer
from app.core.glossary import Glossary
from app.core.history import History
from app.ui.main_window import MainWindow
from app.ui.theme import manager

server = LlamaServer()
win = MainWindow(server, Glossary(), History())
win.show()
qt_app.processEvents()

config.set_key("temperature", 1.35)
config.set_key("top_k", 77)
config.set_key("context", 2048)
config.set_key("threads", 3)
config.set_key("gpu_mode", "cpu")
config.set_key("kv_cache", "f16")
config.set_key("auto_copy", False)
config.set_key("protect_numbers", False)
config.set_key("theme", "dark")
config.set_key("model_path", "D:/custom/my-model.gguf")
config.set_key("autostart", False)

win.temp_spin.setValue(1.35)
win.topk_spin.setValue(77)
win.autocopy_check.setChecked(False)
qt_app.processEvents()

restarts = []
server.restart = lambda: restarts.append(1)

QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)

win._restore_defaults()
qt_app.processEvents()

assert config.get("temperature") == 0.7, config.get("temperature")
assert config.get("top_k") == 20
assert config.get("context") == 8192
assert config.get("threads") == 8
assert config.get("gpu_mode") == "auto"
assert config.get("kv_cache") == "q8_0"
assert config.get("auto_copy") is True
assert config.get("protect_numbers") is True
assert config.get("theme") == "system"
assert config.get("model_path") == "D:/custom/my-model.gguf", "model_path must be preserved"
assert restarts, "engine restart was not triggered"
print("config values restored, engine restart triggered")

assert abs(win.temp_spin.value() - 0.7) < 1e-9, win.temp_spin.value()
assert win.topk_spin.value() == 20
assert win.threads_spin.value() == 8
assert win.gpu_combo.currentData() == "auto"
assert win.ctx_combo.currentData() == 8192
assert win.kv_combo.currentData() == "q8_0"
assert win.autocopy_check.isChecked() is True
assert win.protectnum_check.isChecked() is True
assert win.theme_combo.currentData() == "system"
assert win.model_edit.text() == "D:/custom/my-model.gguf"
print("widgets re-synced to defaults")

assert win.styleSheet() == __import__("app.ui.theme", fromlist=["app_stylesheet"]).app_stylesheet()
print("theme reapplied after reset")

win._loading_settings = True
config.set_key("theme", "dark")
win._sync_settings_widgets()
win._loading_settings = False
config.set_key("theme", "dark")
win._restore_defaults()
qt_app.processEvents()
assert config.get("theme") == "system"
print("second reset cycle OK")

print("ALL RESTORE-DEFAULTS TESTS PASSED")
