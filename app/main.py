import ctypes
import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from app import __version__
from app.controller import AppController
from app.core import config
from app.core.clipboard import read_clipboard_text
from app.core.engine import LlamaServer
from app.core.glossary import Glossary
from app.core.history import History
from app.core.hotkey import HotkeyListener
from app.core.logger import setup_logging
from app.core.paths import APP_NAME, APP_VERSION
from app.core.translator import TranslationService
from app.integrations import contextmenu as contextmenu_mod
from app.integrations import startup
from app.ui.icons import app_icon
from app.ui.main_window import MainWindow
from app.ui.theme import (
    apply_to_application,
    manager as theme_manager,
    tray_menu_stylesheet,
)

log = logging.getLogger(__name__)

IPC_NAME = "MaiTranslatorIPC"


def single_instance_server() -> QLocalServer | None:
    QLocalServer.removeServer(IPC_NAME)
    server = QLocalServer()
    if not server.listen(IPC_NAME):
        return None
    return server


def notify_existing_instance(payload: str) -> bool:
    sock = QLocalSocket()
    sock.connectToServer(IPC_NAME)
    if not sock.waitForConnected(500):
        return False
    sock.write(payload.encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(500)
    sock.disconnectFromServer()
    return True


class MaiTranslatorApp:
    def __init__(self, qt_app: QApplication) -> None:
        self.qt_app = qt_app
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setApplicationVersion(APP_VERSION)
        self.qt_app.setQuitOnLastWindowClosed(False)

        self.server = LlamaServer()
        self.server.request_restart.connect(self.server.restart, Qt.QueuedConnection)
        self.glossary = Glossary()
        self.history = History()
        self.service = TranslationService(self.server, self.glossary, self.history)
        self.controller = AppController(self.service, self.server)

        theme_manager().changed.connect(apply_to_application)
        apply_to_application()
        theme_manager().changed.connect(self.controller.floating.retheme)

        icon = app_icon()
        self.qt_app.setWindowIcon(icon)
        self.main_window = MainWindow(self.server, self.glossary, self.history)
        self.main_window.translate_requested.connect(self._on_main_translate)

        self.service.finished_ok.connect(self._on_main_translate_finished)
        self.service.failed.connect(self._on_main_translate_failed)

        self.tray = QSystemTrayIcon(icon)
        self._build_tray_menu()

        self.ipc = single_instance_server()
        if self.ipc is not None:
            self.ipc.newConnection.connect(self._on_ipc_connection)

        self.hotkey: HotkeyListener | None = None

    def _build_tray_menu(self) -> None:
        menu = QMenu()
        menu.setStyleSheet(tray_menu_stylesheet())
        show_action = QAction("显示主窗口", menu)
        show_action.triggered.connect(self.show_main_window)
        menu.addAction(show_action)

        translate_cb = QAction("翻译剪贴板内容", menu)
        translate_cb.triggered.connect(self.translate_from_clipboard)
        menu.addAction(translate_cb)

        engine_action = QAction("引擎状态：未知", menu)
        engine_action.setEnabled(False)
        self._engine_tray_action = engine_action
        menu.addAction(engine_action)
        self.server.stateChanged.connect(self._on_engine_state_changed)

        menu.addSeparator()

        self.autostart_action = QAction("开机自动启动", menu)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(startup.is_enabled())
        self.autostart_action.toggled.connect(self._on_tray_autostart)
        menu.addAction(self.autostart_action)

        ctx_status = QAction(f"右键菜单：{'已安装' if contextmenu_mod.is_installed() else '未安装（设置页可安装）'}", menu)
        ctx_status.setEnabled(False)
        menu.addAction(ctx_status)

        menu.addSeparator()

        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray_menu = menu
        theme_manager().changed.connect(self._retheme_tray_menu)
        self.tray.setToolTip("MaiTranslator · 本地离线翻译\nAlt + F 划词翻译")
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _retheme_tray_menu(self, *args) -> None:
        self.tray_menu.setStyleSheet(tray_menu_stylesheet())

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_main_window()

    def _on_tray_autostart(self, on: bool) -> None:
        ok = startup.set_enabled(on)
        self.autostart_action.blockSignals(True)
        self.autostart_action.setChecked(startup.is_enabled())
        self.autostart_action.blockSignals(False)
        if not ok:
            QMessageBox.warning(self.main_window, "MaiTranslator", "修改开机自启失败。")

    def _on_engine_state_changed(self, state: str, message: str) -> None:
        text_map = {
            LlamaServer.STATE_STOPPED: "已停止",
            LlamaServer.STATE_LOADING: "加载中…",
            LlamaServer.STATE_READY: f"就绪 · {'GPU' if self.server.gpu_active else 'CPU'} 加速",
            LlamaServer.STATE_ERROR: "错误",
        }
        self._engine_tray_action.setText(f"引擎状态：{text_map.get(state, state)}")
        self.main_window.update_engine_status(state, message)
        if state == LlamaServer.STATE_ERROR:
            self.tray.showMessage(
                "MaiTranslator 引擎错误",
                message or "推理引擎启动失败，请到设置页查看。",
                QSystemTrayIcon.Critical,
                5000,
            )

    def _on_ipc_connection(self) -> None:
        sock = self.ipc.nextPendingConnection()
        if sock is None:
            return
        sock.readyRead.connect(lambda s=sock: self._handle_ipc_payload(s))

    def _handle_ipc_payload(self, sock: QLocalSocket) -> None:
        payload = bytes(sock.readAll()).decode("utf-8", "replace")
        log.info("收到第二实例消息: %r", payload[:200])
        if payload.startswith("file|"):
            path = payload[5:]
            self.show_main_window()
            self.main_window.load_file_for_translation(path)
        else:
            self.show_main_window()
        sock.disconnectFromServer()

    def start(self, file_path: str | None = None, minimized: bool = False) -> None:
        if config.get("hotkey_enabled", True):
            self.hotkey = HotkeyListener()
            self.hotkey.triggered.connect(self.controller.trigger_hotkey_flow)
            self.hotkey.register_failed.connect(
                lambda msg: self.tray.showMessage("热键注册失败", msg, QSystemTrayIcon.Warning, 4000)
            )
            self.hotkey.start()

        if file_path:
            self.show_main_window()
            self.main_window.load_file_for_translation(file_path)
        elif not minimized:
            self.show_main_window()

        self.server.start()
        log.info("%s v%s 启动完成", APP_NAME, APP_VERSION)

    def show_main_window(self) -> None:
        self.main_window.show()
        self.main_window.setWindowState(
            (self.main_window.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive
        )
        self.main_window.raise_()
        self.main_window.activateWindow()

    def translate_from_clipboard(self) -> None:
        text = read_clipboard_text(QApplication.clipboard()).strip()
        if not text:
            self.tray.showMessage(
                "MaiTranslator", "剪贴板中没有文本内容。", QSystemTrayIcon.Information, 2500
            )
            return
        self.controller.start_translation(text)

    def _on_main_translate(self, text: str, forced: str) -> None:
        self.controller.floating.hide()
        self.main_window.set_translate_busy(True)
        self.main_window.result_edit.clear()
        accepted = self.service.submit(text, forced or "", origin="main")
        if not accepted and self.service.busy:
            self.main_window.set_translate_busy(False)
            self.main_window.translate_status.setText("已有翻译任务进行中，请稍候…")

    def _on_main_translate_finished(self, result: dict) -> None:
        if result.get("origin") != "main":
            return
        self.main_window.set_translate_busy(False)
        self.main_window.show_translation_result(result)

    def _on_main_translate_failed(self, message: str, origin: str = "") -> None:
        if origin != "main":
            return
        self.main_window.set_translate_busy(False)
        self.main_window.show_translation_error(message)

    def quit(self) -> None:
        log.info("正在退出…")
        try:
            if self.hotkey is not None:
                self.hotkey.stop()
                self.hotkey.wait(2000)
        except Exception:
            log.exception("停止热键监听失败")
        try:
            self.controller.shutdown()
        except Exception:
            pass
        try:
            self.server.shutdown()
        except Exception:
            log.exception("关闭引擎失败")
        try:
            self.history.close()
        except Exception:
            pass
        self.qt_app.quit()


def main(argv: list[str]) -> int:
    try:
        from app.core.paths import data_dir

        crash_log = os.path.join(str(data_dir()), "crash.log")
        sys.stderr = open(crash_log, "a", encoding="utf-8", buffering=1)
    except Exception:
        pass
    try:
        return _main_inner(argv)
    except SystemExit:
        raise
    except BaseException:
        log.exception("致命错误")
        try:
            import traceback

            tb = traceback.format_exc()
            sys.stderr.write(tb)
            ctypes.windll.user32.MessageBoxW(
                None, f"MaiTranslator 启动失败：\n{tb[-1500:]}", "MaiTranslator", 0x10
            )
        except Exception:
            pass
        return 1


def _main_inner(argv: list[str]) -> int:
    setup_logging()
    log.info("=" * 60)
    log.info("%s v%s 启动，参数: %s", APP_NAME, APP_VERSION, argv)

    file_path: str | None = None
    if "--file" in argv:
        idx = argv.index("--file")
        if idx + 1 < len(argv):
            file_path = argv[idx + 1]
    minimized = "--minimized" in argv

    payload = f"file|{file_path}" if file_path else "show"
    if notify_existing_instance(payload):
        log.info("检测到已有实例运行，已通知其显示窗口")
        return 0

    qt_app = QApplication(sys.argv[:1])
    qt_app.setQuitOnLastWindowClosed(False)

    app = MaiTranslatorApp(qt_app)
    app.start(file_path=file_path, minimized=minimized)
    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
