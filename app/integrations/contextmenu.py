import logging
import sys
from pathlib import Path

try:
    import winreg
except ImportError:
    winreg = None

log = logging.getLogger(__name__)

SHELL_KEY = r"Software\Classes\*\shell\MaiTranslator"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "MaiTranslator"


def exe_path() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve())
    return ""


def command_line() -> str:
    exe = exe_path()
    if not exe:
        python = sys.executable
        main = Path(__file__).resolve().parents[1] / "main.py"
        return f'"{python}" "{main}" --file "%1"'
    return f'"{exe}" --file "%1"'


def icon_path() -> str:
    exe = exe_path()
    if exe:
        return exe
    return ""


def is_installed() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SHELL_KEY):
            return True
    except OSError:
        return False


def install() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, SHELL_KEY) as key:
            winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, "使用 MaiTranslator 翻译")
            icon = icon_path()
            if icon:
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, SHELL_KEY + r"\command") as key:
            winreg.SetValueEx(key, None, 0, winreg.REG_SZ, command_line())
        log.info("右键菜单已安装")
        return True
    except OSError as e:
        log.error("右键菜单安装失败: %s", e)
        return False


def uninstall() -> bool:
    if winreg is None:
        return False
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, SHELL_KEY + r"\command")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, SHELL_KEY)
        log.info("右键菜单已卸载")
        return True
    except FileNotFoundError:
        return True
    except OSError as e:
        log.error("右键菜单卸载失败: %s", e)
        return False
