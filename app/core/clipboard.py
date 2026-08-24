import ctypes
import ctypes.wintypes as wt
import logging
import time

log = logging.getLogger(__name__)

user32 = ctypes.windll.user32

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_C = 0x43


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wt.WORD),
        ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wt.ULONG)),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wt.LONG),
        ("dy", wt.LONG),
        ("mouseData", wt.DWORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wt.ULONG)),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wt.DWORD),
        ("wParamL", wt.WORD),
        ("wParamH", wt.WORD),
    ]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT), ("hi", _HARDWAREINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def foreground_window() -> int:
    return int(user32.GetForegroundWindow() or 0)


def foreground_title(hwnd: int) -> str:
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def send_ctrl_c() -> bool:
    inputs = (_INPUT * 4)()

    def set_key(i: int, vk: int, flags: int = 0) -> None:
        inputs[i].type = INPUT_KEYBOARD
        inputs[i].ki.wVk = vk
        inputs[i].ki.dwFlags = flags

    set_key(0, VK_CONTROL)
    set_key(1, VK_C)
    set_key(2, VK_C, KEYEVENTF_KEYUP)
    set_key(3, VK_CONTROL, KEYEVENTF_KEYUP)
    sent = user32.SendInput(4, ctypes.pointer(inputs[0]), ctypes.sizeof(_INPUT))
    if sent != 4:
        log.warning("SendInput 发送失败: sent=%s err=%s", sent, ctypes.GetLastError())
        return False
    return True


def clipboard_sequence() -> int:
    return int(user32.GetClipboardSequenceNumber())


def read_clipboard_text(qt_clipboard, retries: int = 4, delay: float = 0.12) -> str:
    for i in range(retries):
        try:
            text = qt_clipboard.text()
            return text
        except Exception as e:
            log.warning("读取剪贴板失败（第 %d 次）: %s", i + 1, e)
            time.sleep(delay)
    return ""


def write_clipboard_text(qt_clipboard, text: str, retries: int = 4, delay: float = 0.12) -> bool:
    for i in range(retries):
        try:
            qt_clipboard.setText(text)
            time.sleep(0.05)
            if qt_clipboard.text() == text:
                return True
        except Exception as e:
            log.warning("写入剪贴板失败（第 %d 次）: %s", i + 1, e)
        time.sleep(delay)
    log.error("剪贴板写入最终失败")
    return False
