import io
import os
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="mt_histsel_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

qt_app = QApplication(sys.argv[:1])

from app.core.logger import setup_logging

setup_logging()

from app.core import config

config.set_key("theme", "light")

from app.core.engine import LlamaServer
from app.core.glossary import Glossary
from app.core.history import History
import app.ui.main_window as mw
from app.ui.main_window import MainWindow
from app.ui.theme import apply_to_application, current_palette

apply_to_application()

history = History()
for i in range(5):
    history.add("zh", "en", f"src {i}", f"tgt {i}", 100.0)

server = LlamaServer()
win = MainWindow(server, Glossary(), history)
win.show()
qt_app.processEvents()
win.tabs.setCurrentWidget(win.tab_history)
qt_app.processEvents()

table = win.history_table
print(f"rows={table.rowCount()} mode={table.selectionMode()} behavior={table.selectionBehavior()}")
assert table.rowCount() == 5


def click_row(row, modifier=Qt.NoModifier):
    viewport = table.viewport()
    rect = table.visualItemRect(table.item(row, 2))
    QTest.mouseClick(viewport, Qt.LeftButton, modifier, rect.center())
    qt_app.processEvents()
    return sorted({it.row() for it in table.selectedItems()})


detail_shown = []


class _FakeDetailDialog:
    def __init__(self, record, parent=None):
        self.record = dict(record)
        self.parent = parent
        detail_shown.append(self.record)

    def exec(self):
        pass


_real_detail_cls = mw.HistoryDetailDialog
mw.HistoryDetailDialog = _FakeDetailDialog

sel = click_row(1)
print("plain click row 1 ->", sel)
assert sel == [1], "plain left-click must select exactly one record"
assert len(detail_shown) == 1, "plain click must open the detail dialog"
assert detail_shown[0]["id"] == 4 and detail_shown[0]["source"] == "src 3", (
    "dialog must show the clicked record (rows are newest-first)"
)
assert detail_shown[0]["result"] == "tgt 3"
print("plain-click popup OK:", detail_shown[0]["created_at"], detail_shown[0]["source"])

sel = click_row(4, Qt.ShiftModifier)
print("shift+click row 4 ->", sel)
assert sel == [1, 2, 3, 4], "shift+click must select a contiguous range"
assert len(detail_shown) == 1, "shift+click must NOT open the detail dialog"

sel = click_row(0, Qt.ControlModifier)
print("ctrl+click row 0 ->", sel)
assert sel == [0, 1, 2, 3, 4], "ctrl+click must extend the selection"
assert len(detail_shown) == 1, "ctrl+click must NOT open the detail dialog"

print("selection label:", win.history_sel_label.text())
assert win.history_sel_label.text() == "已选 5/5 条"


def render_table():
    img = QImage(table.viewport().size(), QImage.Format_ARGB32)
    table.viewport().render(img)
    return img


def has_accent_pixels(img) -> int:
    accent = (0x25, 0x63, 0xEB)  # light theme accent #2563eb
    count = 0
    for y in range(0, img.height(), 3):
        for x in range(0, img.width(), 3):
            p = img.pixelColor(x, y)
            if (p.red(), p.green(), p.blue()) == accent:
                count += 1
    return count


accent_hits = has_accent_pixels(render_table())
print(f"accent-colored sampled pixels while rows selected: {accent_hits}")
assert accent_hits > 20, "selected rows must be painted with a clearly visible highlight"

# Ctrl+A select all (standard Windows)
QTest.keyClick(table, Qt.Key_A, Qt.ControlModifier)
qt_app.processEvents()
sel = sorted({it.row() for it in table.selectedItems()})
print("ctrl+a ->", sel)
assert sel == [0, 1, 2, 3, 4]

# Esc clears selection (standard Windows)
QTest.keyClick(table, Qt.Key_Escape)
qt_app.processEvents()
sel = sorted({it.row() for it in table.selectedItems()})
print("esc ->", sel, "| label:", win.history_sel_label.text())
assert sel == []
assert win.history_sel_label.text() == "未选择记录"

# plain click again + Delete key deletes selected records
sel = click_row(2)
assert sel == [2]
assert len(detail_shown) == 2 and detail_shown[1]["source"] == "src 2", (
    "each plain click must show its own record"
)
ids = win._selected_history_ids()
print("delete-key on ids:", ids)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QTest.keyClick(table, Qt.Key_Delete)
qt_app.processEvents()
remaining = history.count()
print("remaining after Delete key:", remaining)
assert remaining == 4, "Delete key must delete the selected record"

# Enter key opens details of the current row (rows are id-desc: 5,4,2,1)
table.setCurrentCell(2, 0)
qt_app.processEvents()
QTest.keyClick(table, Qt.Key_Return)
qt_app.processEvents()
assert len(detail_shown) == 3, "Enter must open the detail dialog for the current row"
assert detail_shown[2]["source"] == "src 1", "Enter must show the record under the cursor"
print("enter-key popup OK:", detail_shown[2]["source"])

# real dialog renders the full un-truncated content of its record
mw.HistoryDetailDialog = _real_detail_cls
long_src = "很长的原文\n" * 80
long_dst = "a very long result text\n" * 80
hid = history.add("zh", "en", long_src, long_dst, 1234.0)
win._refresh_history()
rec = history.get(hid)
assert rec is not None and rec["chars"] == len(long_src)
dlg = _real_detail_cls(rec, win)
assert dlg.source_view.toPlainText() == long_src, "popup must show full source text"
assert dlg.result_view.toPlainText() == long_dst, "popup must show full result text"
assert f"#{hid}" in dlg.windowTitle()
assert dlg.parent() is win
dlg.close()
print("detail dialog content OK (full text, no truncation)")

# empty-selection delete shows guidance instead of doing nothing silently
box = {}
QMessageBox.information = staticmethod(lambda *a, **k: box.setdefault("called", True))
win._delete_selected_history()
assert box.get("called"), "empty selection must show guidance message"
print("empty-selection guidance OK")

win.close()
print("ALL HISTORY SELECTION TESTS PASSED")
