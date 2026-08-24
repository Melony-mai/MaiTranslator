import ctypes
import ctypes.wintypes as wt
import io
import json
import os
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from PySide6.QtWidgets import QApplication

qt_app = QApplication(sys.argv[:1])
from PySide6.QtGui import QGuiApplication

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
gdi32.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
        ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def find_main():
    return user32.FindWindowW(None, "MaiTranslator · 本地离线翻译")


def capture(tag):
    hwnd = find_main()
    assert hwnd, "main window not found"
    user32.ShowWindow(hwnd, 9)
    time.sleep(0.8)
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc = user32.GetWindowDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(memdc, bmp)
    ok = user32.PrintWindow(hwnd, memdc, 0x2)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    buf = (ctypes.c_ubyte * (w * h * 4))()
    gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)

    from PySide6.QtGui import QImage

    img = QImage(buf, w, h, w * 4, QImage.Format_ARGB32).copy()
    out = Path(os.environ["TEMP"]) / f"packaged_{tag}.png"
    img.save(str(out))
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hdc)
    print("saved", out.name, w, "x", h, "printwindow_ok:", bool(ok))


cfg = Path(os.environ["APPDATA"]) / "MaiTranslator" / "config.json"
data = json.loads(cfg.read_text(encoding="utf-8"))

data["theme"] = "light"
cfg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
os.system("taskkill /f /im MaiTranslator.exe >nul 2>&1")
time.sleep(2)
os.startfile(r"D:\python\code\MaiTranslator\dist\MaiTranslator\MaiTranslator.exe")
time.sleep(14)
capture("light")

data["theme"] = "dark"
cfg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
os.system("taskkill /f /im MaiTranslator.exe >nul 2>&1")
time.sleep(2)
os.startfile(r"D:\python\code\MaiTranslator\dist\MaiTranslator\MaiTranslator.exe")
time.sleep(14)
capture("dark")
print("DONE")
