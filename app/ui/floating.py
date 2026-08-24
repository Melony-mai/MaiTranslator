import logging

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.clipboard import write_clipboard_text
from app.ui.theme import current_palette, floating_stylesheet

log = logging.getLogger(__name__)


class FloatingWindow(QWidget):
    copy_requested = Signal(str)
    closed = Signal()

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowTitle("MaiTranslator")
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(520, 420)
        self._drag_pos = None
        self._dots_timer = QTimer(self)
        self._dots_timer.setInterval(350)
        self._dots_timer.timeout.connect(self._animate_dots)
        self._dots = 0
        self._translation = ""
        self._auto_copied = False
        self._status_state = "idle"
        self._build_ui()
        self.retheme()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("card")
        outer.addWidget(card)

        root = QVBoxLayout(card)
        root.setContentsMargins(14, 10, 14, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        self.dir_badge = QLabel("中 → 英")
        self.dir_badge.setObjectName("dirBadge")
        header.addWidget(self.dir_badge)
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        header.addWidget(self.status_label)
        header.addStretch(1)
        self.copy_btn = QPushButton("复制译文")
        self.copy_btn.setObjectName("copyBtn")
        self.copy_btn.clicked.connect(self.copy_translation)
        header.addWidget(self.copy_btn)
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        root.addLayout(header)

        src_title = QLabel("原文")
        src_title.setObjectName("title")
        root.addWidget(src_title)
        self.source_view = self._make_readonly_view(72)
        root.addWidget(self.source_view)

        dst_title = QLabel("译文")
        dst_title.setObjectName("title")
        root.addWidget(dst_title)
        self.result_view = self._make_readonly_view(120)
        root.addWidget(self.result_view, stretch=1)

        footer = QHBoxLayout()
        self.toast_label = QLabel("")
        self.toast_label.setObjectName("toastLabel")
        footer.addWidget(self.toast_label)
        footer.addStretch(1)
        hint = QLabel("Enter 复制译文 · Esc 关闭")
        hint.setObjectName("hintLabel")
        footer.addWidget(hint)
        root.addLayout(footer)

    def _make_readonly_view(self, min_height: int) -> QTextEdit:
        view = QTextEdit()
        view.setReadOnly(True)
        view.setMinimumHeight(min_height)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        return view

    def retheme(self) -> None:
        pal = current_palette()
        self.setStyleSheet(floating_stylesheet(pal))
        colors = {
            "idle": pal["text_muted"],
            "busy": pal["warning"],
            "done": pal["success"],
            "error": pal["error"],
        }
        self._status_colors = colors
        self._apply_status_color()

    def _apply_status_color(self) -> None:
        color = self._status_colors.get(self._status_state, self._status_colors["idle"])
        self.status_label.setStyleSheet(f"color:{color}; font-size:12px;")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key_Escape:
            self.close()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self.copy_translation()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def begin_translation(self, source_text: str, direction_text: str) -> None:
        self._translation = ""
        self._auto_copied = False
        self.dir_badge.setText(direction_text)
        self.source_view.setPlainText(source_text)
        self.result_view.setPlainText("")
        self._dots = 0
        self._set_status_busy("正在本地翻译中")
        self.show_at_cursor()

    def _set_status_busy(self, prefix: str) -> None:
        self._status_prefix = prefix
        self._status_state = "busy"
        self._apply_status_color()
        self.status_label.setText(prefix + "." * self._dots)

    def set_result(self, result_text: str, duration_ms: float, extra_note: str = "") -> None:
        self._dots_timer.stop()
        self._translation = result_text
        self.result_view.setPlainText(result_text)
        secs = duration_ms / 1000.0
        note = f" · {extra_note}" if extra_note else ""
        self._status_state = "done"
        self._apply_status_color()
        self.status_label.setText(f"完成 · {secs:.1f} 秒{note}")
        self.result_view.verticalScrollBar().setValue(0)

    def set_error(self, message: str) -> None:
        self._dots_timer.stop()
        self._status_state = "error"
        self._apply_status_color()
        self.status_label.setText("翻译失败")
        self.result_view.setPlainText(message)

    def set_translation_ready_to_copy(self, text: str) -> None:
        self._translation = text

    def _animate_dots(self) -> None:
        self._dots = (self._dots + 1) % 4
        self.status_label.setText(getattr(self, "_status_prefix", "正在本地翻译中") + "." * self._dots)

    def show_at_cursor(self) -> None:
        cursor = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor)
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        w, h = self.width(), min(self.height(), int(geo.height() * 0.75))
        x = cursor.x() - w // 2
        y = cursor.y() + 24
        x = max(geo.left() + 8, min(x, geo.right() - w - 8))
        y = max(geo.top() + 8, min(y, geo.bottom() - h - 8))
        self.setGeometry(x, y, w, h)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def copy_translation(self) -> None:
        if not self._translation:
            return
        cb = QApplication.clipboard()
        if write_clipboard_text(cb, self._translation):
            self.toast_label.setText("已复制到剪贴板")
            self.toast_label.setStyleSheet(
                f"color:{current_palette()['success']}; font-size:12px;"
            )
            QTimer.singleShot(1600, lambda: self.toast_label.setText(""))
        else:
            self.toast_label.setText("复制失败，请手动选择文本复制")
            self.toast_label.setStyleSheet(
                f"color:{current_palette()['error']}; font-size:12px;"
            )

    def mark_auto_copied(self) -> None:
        self._auto_copied = True

    def closeEvent(self, event) -> None:
        self._dots_timer.stop()
        self.closed.emit()
        super().closeEvent(event)
