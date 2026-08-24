import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

qt_app = QApplication(sys.argv[:1])
cb = qt_app.clipboard()

def step1():
    print("seq before:", cb.supportsSelection())
    cb.setText("Hello clipboard 你好剪贴板")
    print("immediate read:", repr(cb.text()))

    def step2():
        qt_app.processEvents()
        print("after events read:", repr(cb.text()))
        cb.setText("second write 测试")
        loop = []

        def poll():
            loop.append(1)
            t = cb.text()
            if t == "second write 测试" or len(loop) > 10:
                print(f"poll#{len(loop)} read:", repr(t))
                qt_app.exit(0)
            else:
                QTimer.singleShot(50, poll)

        poll()

    QTimer.singleShot(200, step2)

QTimer.singleShot(100, step1)
sys.exit(qt_app.exec())
