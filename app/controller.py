import logging
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from app.core import clipboard as cb
from app.core.config import get
from app.core.engine import LlamaServer
from app.core.translator import TranslationService
from app.ui.floating import FloatingWindow

log = logging.getLogger(__name__)


class AppController(QObject):
    def __init__(self, service: TranslationService, server: LlamaServer) -> None:
        super().__init__()
        self.service = service
        self.server = server
        self.floating = FloatingWindow()
        self._pending_source = ""
        self._pending_forced: str | None = None
        self._capture_hwnd = 0
        service.finished_ok.connect(self._on_translated)
        service.failed.connect(self._on_failed)
        self.floating.copy_requested.connect(self._on_copy_requested)

    @staticmethod
    def direction_text(src: str, tgt: str) -> str:
        names = {"zh": "中", "en": "英"}
        return f"{names.get(src, src)} → {names.get(tgt, tgt)}"

    def trigger_hotkey_flow(self) -> None:
        try:
            self._capture_hwnd = cb.foreground_window()
            title = cb.foreground_title(self._capture_hwnd)
            log.info("热键触发，前台窗口: %s", title[:80])
            seq_before = cb.clipboard_sequence()
            if self._capture_hwnd and "maitranslator" not in title.lower():
                cb.send_ctrl_c()
                delay_ms = int(get("capture_delay_ms", 260))
                deadline = time.monotonic() + delay_ms / 1000.0 + 0.5
                while time.monotonic() < deadline:
                    if cb.clipboard_sequence() != seq_before:
                        break
                    QApplication.processEvents()
                    time.sleep(0.03)
            else:
                log.info("前台是本应用或无前台窗口，直接使用当前剪贴板")
            text = cb.read_clipboard_text(QApplication.clipboard()).strip()
            if not text:
                log.warning("未获取到任何文本（剪贴板为空且无选中文本）")
                return
            if len(text) > 20000:
                text = text[:20000]
                log.info("文本过长，已截断到 20000 字符")
            self.start_translation(text, forced=None)
        except Exception:
            log.exception("热键流程异常")

    def start_translation(self, text: str, forced: str | None = None) -> None:
        if not text.strip():
            return
        self._pending_source = text
        self._pending_forced = forced or None
        src_guess, tgt_guess = self._guess_direction(text, forced)
        self.floating.begin_translation(text, self.direction_text(src_guess, tgt_guess))
        self.service.submit(text, forced or "")

    @staticmethod
    def _guess_direction(text: str, forced: str | None) -> tuple[str, str]:
        from app.core import langdetect

        return langdetect.direction(text, forced)

    def _on_translated(self, result: dict) -> None:
        direction = self.direction_text(result["src_lang"], result["tgt_lang"])
        note_bits = []
        if result.get("used_terms"):
            note_bits.append("词表已生效")
        if result.get("missing_terms"):
            log.info("词表未完全命中: %s", result["missing_terms"])
        auto_copy = bool(get("auto_copy", True))
        if auto_copy:
            from app.core.clipboard import write_clipboard_text

            ok = write_clipboard_text(QApplication.clipboard(), result["result"])
            if ok:
                self.floating.set_translation_ready_to_copy(result["result"])
                note_bits.append("已自动复制")
            else:
                note_bits.append("自动复制失败，请手动复制")
        self.floating.set_result(
            result["result"], result.get("duration_ms", 0.0), " · ".join(note_bits)
        )

    def _on_failed(self, message: str) -> None:
        log.error("翻译失败: %s", message)
        self.floating.set_error(f"翻译失败：{message}\n\n请确认推理引擎已启动（设置页可查看状态）。")

    def _on_copy_requested(self) -> None:
        pass

    def shutdown(self) -> None:
        self.floating.close()
