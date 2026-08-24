import logging
import sys
from pathlib import Path

try:
    import winreg
except ImportError:
    winreg = None

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "MaiTranslator"


def _launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}" --minimized'
    main_py = Path(__file__).resolve().parents[1] / "main.py"
    return f'"{sys.executable}" "{main_py}" --minimized'


def is_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            val, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _launch_command())
        log.info("已启用开机自启")
        return True
    except OSError as e:
        log.error("设置开机自启失败: %s", e)
        return False


def disable() -> bool:
    if winreg is None:
        return True
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
        log.info("已禁用开机自启")
        return True
    except FileNotFoundError:
        return True
    except OSError as e:
        log.error("取消开机自启失败: %s", e)
        return False


def set_enabled(on: bool) -> bool:
    return enable() if on else disable()
