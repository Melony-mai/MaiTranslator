import ctypes
import ctypes.wintypes
import logging

from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
VK_F = 0x46
HOTKEY_ID = 0x4D54


class HotkeyListener(QThread):
    triggered = Signal()
    register_failed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread_id = 0
        self._registered = False

    @staticmethod
    def hotkey_text() -> str:
        return "Alt + F"

    def run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        ok = user32.RegisterHotKey(None, HOTKEY_ID, MOD_ALT | MOD_NOREPEAT, VK_F)
        if not ok:
            err = kernel32.GetLastError()
            log.error("注册全局热键失败 (GetLastError=%s)，热键可能被占用", err)
            self.register_failed.emit(f"全局热键 {self.hotkey_text()} 注册失败（错误码 {err}），可能已被其他程序占用。")
            return
        self._registered = True
        log.info("全局热键 %s 已注册", self.hotkey_text())
        msg = ctypes.wintypes.MSG()
        lpmsg = ctypes.byref(msg)
        while True:
            r = user32.GetMessageW(lpmsg, None, 0, 0)
            if r <= 0:
                break
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.triggered.emit()
        if self._registered:
            user32.UnregisterHotKey(None, HOTKEY_ID)
            self._registered = False
        log.info("热键监听线程退出")

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
