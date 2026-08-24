import ctypes
import ctypes.wintypes as wt
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

user32.GetClipboardData.restype = wt.HANDLE
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def press_hotkey():
    seq = [(0x12, 0), (0x46, 0), (0x46, KEYEVENTF_KEYUP), (0x12, KEYEVENTF_KEYUP)]
    arr = (INPUT * len(seq))()
    for i, (vk, flags) in enumerate(seq):
        arr[i].type = INPUT_KEYBOARD
        arr[i].ki.wVk = vk
        arr[i].ki.dwFlags = flags
    sent = user32.SendInput(len(seq), ctypes.pointer(arr[0]), ctypes.sizeof(INPUT))
    print("hotkey sent:", sent == len(seq))


def clip_text():
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.2)
    else:
        return None
    try:
        h = user32.GetClipboardData(13)
        if not h:
            return ""
        p = kernel32.GlobalLock(h)
        s = (ctypes.c_wchar_p(p).value or "") if p else ""
        kernel32.GlobalUnlock(h)
        return s
    finally:
        user32.CloseClipboard()


def set_clip(text):
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.2)
    else:
        return False
    try:
        user32.EmptyClipboard()
        g = kernel32.GlobalAlloc(0x2002, 2 * (len(text) + 1))
        p = kernel32.GlobalLock(g)
        ctypes.memmove(p, ctypes.create_unicode_buffer(text), 2 * (len(text) + 1))
        kernel32.GlobalUnlock(g)
        user32.SetClipboardData(13, g)
        return True
    finally:
        user32.CloseClipboard()


tests = [
    ("The quick brown fox jumps over the lazy dog.", "zh"),
    ("人工智能正在改变世界，未来充满无限可能。", "en"),
]

for i, (text, expect_lang) in enumerate(tests, 1):
    assert set_clip(text), "set clipboard failed"
    time.sleep(0.3)
    print(f"--- test {i}: seeded clipboard ({expect_lang} expected) ---")
    press_hotkey()
    deadline = time.time() + 90
    got = None
    while time.time() < deadline:
        t = clip_text()
        if t and t != text:
            got = t
            break
        time.sleep(1.0)
    print("RESULT:", repr(got[:120]) if got else "TIMEOUT")
    assert got, f"test {i}: no translation appeared"
    has_cjk = any("\u4e00" <= c <= "\u9fff" for c in got)
    has_latin = any(c.isascii() and c.isalpha() for c in got)
    if expect_lang == "zh":
        assert has_cjk, f"expected Chinese output, got: {got}"
    else:
        assert has_latin and not has_cjk, f"expected English output, got: {got}"

print("HOTKEY E2E TESTS PASSED")
