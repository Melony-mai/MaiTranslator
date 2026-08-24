import io
import os
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="maitranslator_gui_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

qt_app = QApplication(sys.argv[:1])

from app.core.logger import setup_logging

setup_logging()
from app.core import config
from app.core.clipboard import clipboard_sequence, read_clipboard_text, send_ctrl_c
from app.core.engine import LlamaServer
from app.core.glossary import Glossary
from app.core.history import History
from app.core.hotkey import HotkeyListener
from app.core.translator import TranslationService
from app.controller import AppController
from app.ui.main_window import MainWindow

server = LlamaServer()
glossary = Glossary()
history = History()
service = TranslationService(server, glossary, history)
controller = AppController(service, server)
win = MainWindow(server, glossary, history)

errors = []
hotkey = HotkeyListener()
hotkey.register_failed.connect(errors.append)


def check_hotkey_registered():
    if errors:
        print("HOTKEY REGISTER FAILED:", errors[0])
        qt_app.exit(2)
    else:
        print("HOTKEY REGISTERED OK (Alt + F)")


QTimer.singleShot(1500, check_hotkey_registered)

state = {"phase": 0}


def phase_machine():
    s = server.state
    if state["phase"] == 0 and s == LlamaServer.STATE_READY:
        state["phase"] = 1
        print("[gui-test] engine ready, testing floating window flow...")
        controller.start_translation("人工智能正在改变世界。")
    if state["phase"] == 1 and controller.floating.isVisible() and not service.busy:
        fw = controller.floating
        txt = fw.result_view.toPlainText()
        print("[gui-test] floating result:", txt[:80])
        print("[gui-test] status label:", fw.status_label.text())
        assert len(txt) > 3, "floating window has no translation"
        state["phase"] = 2

        clip = read_clipboard_text(qt_app.clipboard())
        print("[gui-test] clipboard after auto-copy:", clip[:80])
        assert clip == txt or clip == fw._translation, "clipboard != translation"

        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent

        ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        qt_app.sendEvent(fw, ev)
        assert not fw.isVisible(), "Esc did not close floating window"
        print("[gui-test] Esc closes floating window OK")

        win.show_translation_result(
            {"source": "测试", "result": "test", "src_lang": "zh", "tgt_lang": "en", "duration_ms": 12.0}
        )
        assert win.history_table.rowCount() >= 1, "history table empty"
        win.tabs.setCurrentIndex(2)
        assert win.glossary_table.rowCount() == 0, "glossary should start empty"
        win.tabs.setCurrentIndex(3)
        assert win.engine_status.text(), "engine status empty"
        print("[gui-test] main window tabs OK")
        qt_app.exit(0)


timer = QTimer()
timer.setInterval(300)
timer.timeout.connect(phase_machine)
timer.start()

hotkey.start()
server.start()


def finish():
    print("GUI SMOKE TEST TIMEOUT")
    qt_app.exit(3)


QTimer.singleShot(180000, finish)
rc = qt_app.exec()
print("EXIT CODE:", rc)
if rc == 0:
    print("ALL GUI TESTS PASSED")
