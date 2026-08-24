import logging
from string import Template

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette

from app.core import config

log = logging.getLogger(__name__)

LIGHT = {
    "bg": "#f3f5f9",
    "surface": "#ffffff",
    "surface_alt": "#fafbfd",
    "text": "#1c2230",
    "text_secondary": "#39414f",
    "text_muted": "#5d6676",
    "border": "#d4d9e3",
    "border_strong": "#b9c2d2",
    "accent": "#2563eb",
    "accent_hover": "#1d4fd7",
    "accent_pressed": "#1a44ba",
    "on_accent": "#ffffff",
    "secondary_btn": "#e8ecf4",
    "secondary_btn_hover": "#dbe1ee",
    "secondary_btn_pressed": "#ccd4e4",
    "secondary_btn_text": "#273043",
    "danger": "#dc4a3e",
    "danger_hover": "#c43d32",
    "input_bg": "#ffffff",
    "grid": "#e6eaf1",
    "header_bg": "#eef1f7",
    "header_text": "#333c50",
    "selection_bg": "#cfe0ff",
    "selection_text": "#10254a",
    "badge_bg": "#dbe7ff",
    "badge_text": "#17408f",
    "success": "#157347",
    "warning": "#8f6000",
    "error": "#bb2d20",
    "disabled_bg": "#e4e8f0",
    "disabled_text": "#6f7889",
    "view_bg": "#ffffff",
    "card": "#ffffff",
    "shadow_border": "#c9d1de",
}

DARK = {
    "bg": "#12141a",
    "surface": "#1c1f28",
    "surface_alt": "#21252f",
    "text": "#e9edf4",
    "text_secondary": "#ccd4e2",
    "text_muted": "#a3adc0",
    "border": "#3a4254",
    "border_strong": "#4a5470",
    "accent": "#5b8dff",
    "accent_hover": "#74a1ff",
    "accent_pressed": "#4879e8",
    "on_accent": "#0a1322",
    "secondary_btn": "#2b3140",
    "secondary_btn_hover": "#374053",
    "secondary_btn_pressed": "#232937",
    "secondary_btn_text": "#e6ebf4",
    "danger": "#e05548",
    "danger_hover": "#ea6a5e",
    "input_bg": "#171a23",
    "grid": "#2a3040",
    "header_bg": "#262b38",
    "header_text": "#d5dcea",
    "selection_bg": "#31518c",
    "selection_text": "#eef4ff",
    "badge_bg": "#263754",
    "badge_text": "#9cc2ff",
    "success": "#57d78d",
    "warning": "#ecc76a",
    "error": "#f08a7e",
    "disabled_bg": "#262b36",
    "disabled_text": "#6f7889",
    "view_bg": "#15171e",
    "card": "#1c1f28",
    "shadow_border": "#000000",
}

PALETTES = {"light": LIGHT, "dark": DARK}


def resolve_scheme(prefer: str | None = None) -> str:
    value = prefer or config.get("theme", "system")
    if value in ("light", "dark"):
        return value
    try:
        scheme = QGuiApplication.styleHints().colorScheme()
        if scheme is not None and int(scheme) == int(Qt.ColorScheme.Dark):
            return "dark"
    except Exception:
        pass
    return "light"


def current_palette() -> dict:
    return PALETTES[resolve_scheme()]


def _color(hexstr: str) -> QColor:
    return QColor(hexstr)


def build_qpalette(pal: dict) -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, _color(pal["bg"]))
    p.setColor(QPalette.WindowText, _color(pal["text"]))
    p.setColor(QPalette.Base, _color(pal["input_bg"]))
    p.setColor(QPalette.AlternateBase, _color(pal["surface_alt"]))
    p.setColor(QPalette.Text, _color(pal["text"]))
    p.setColor(QPalette.Button, _color(pal["secondary_btn"]))
    p.setColor(QPalette.ButtonText, _color(pal["secondary_btn_text"]))
    p.setColor(QPalette.ToolTipBase, _color(pal["surface"]))
    p.setColor(QPalette.ToolTipText, _color(pal["text"]))
    p.setColor(QPalette.Highlight, _color(pal["selection_bg"]))
    p.setColor(QPalette.HighlightedText, _color(pal["selection_text"]))
    p.setColor(QPalette.Link, _color(pal["accent"]))
    p.setColor(QPalette.PlaceholderText, _color(pal["text_muted"]))
    for group in (QPalette.Disabled, QPalette.Inactive):
        p.setColor(
            group,
            QPalette.WindowText,
            _color(pal["disabled_text"]) if group == QPalette.Disabled else _color(pal["text"]),
        )
        p.setColor(
            group,
            QPalette.Text,
            _color(pal["disabled_text"]) if group == QPalette.Disabled else _color(pal["text"]),
        )
        p.setColor(
            group,
            QPalette.ButtonText,
            _color(pal["disabled_text"]) if group == QPalette.Disabled else _color(pal["secondary_btn_text"]),
        )
    return p


APP_QSS = """
QWidget#mainWindow { background: $bg; }
QWidget { color: $text; }
QLabel { background: transparent; }

QTabWidget::pane {
    border: 1px solid $border; border-radius: 8px;
    background: $surface; top: -1px;
}
QTabBar::tab {
    background: transparent; color: $text_muted; padding: 8px 22px;
    font-size: 14px; border-top-left-radius: 8px; border-top-right-radius: 8px;
}
QTabBar::tab:selected { background: $surface; color: $accent; font-weight: bold; }
QTabBar::tab:hover:!selected { color: $accent; background: $surface_alt; }

QPushButton {
    background: $accent; color: $on_accent; border: none; border-radius: 6px;
    padding: 7px 18px; font-size: 13px;
}
QPushButton:hover { background: $accent_hover; }
QPushButton:pressed { background: $accent_pressed; }
QPushButton:disabled { background: $disabled_bg; color: $disabled_text; }
QPushButton.secondary {
    background: $secondary_btn; color: $secondary_btn_text;
}
QPushButton.secondary:hover { background: $secondary_btn_hover; }
QPushButton.secondary:pressed { background: $secondary_btn_pressed; }
QPushButton.danger { background: $danger; color: $on_accent; }
QPushButton.danger:hover { background: $danger_hover; }

QTextEdit, QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    border: 1px solid $border; border-radius: 6px; padding: 6px;
    background: $input_bg; color: $text; font-size: 13px;
    selection-background-color: $selection_bg; selection-color: $selection_text;
}
QTextEdit:focus, QPlainTextEdit:focus, QLineEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid $accent;
}
QComboBox:disabled { background: $disabled_bg; color: $disabled_text; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: $surface; color: $text; border: 1px solid $border_strong;
    selection-background-color: $selection_bg; selection-color: $selection_text;
    outline: none;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background: $secondary_btn; border: none; width: 16px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background: $secondary_btn_hover;
}

QCheckBox { color: $text; spacing: 7px; }
QCheckBox:disabled { color: $disabled_text; }

QTableWidget {
    border: 1px solid $border; border-radius: 6px; gridline-color: $grid;
    background: $view_bg; alternate-background-color: $surface_alt;
    selection-background-color: $selection_bg; selection-color: $selection_text;
}
QHeaderView::section {
    background: $header_bg; color: $header_text; border: none;
    padding: 6px; font-weight: bold;
}
QTableCornerButton::section { background: $header_bg; border: none; }

QScrollBar:vertical {
    background: transparent; width: 11px; margin: 2px;
}
QScrollBar::handle:vertical {
    background: $border_strong; border-radius: 4px; min-height: 28px;
}
QScrollBar::handle:vertical:hover { background: $accent; }
QScrollBar:horizontal {
    background: transparent; height: 11px; margin: 2px;
}
QScrollBar::handle:horizontal {
    background: $border_strong; border-radius: 4px; min-width: 28px;
}
QScrollBar::handle:horizontal:hover { background: $accent; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QLabel#hint { color: $text_muted; font-size: 12px; }
QToolTip {
    background: $surface; color: $text; border: 1px solid $border_strong;
    padding: 4px;
}

QScrollArea, QScrollArea > QWidget > QWidget { background: $bg; }
QScrollArea > QWidget > QScrollArea { background: $input_bg; }

QGroupBox {
    font-weight: bold; border: 1px solid $border; border-radius: 8px;
    margin-top: 12px; background: $surface_alt; color: $text_secondary;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 4px; color: $text_secondary;
}

QMessageBox { background: $surface; }
"""

FLOATING_QSS = """
QFrame#card { background: $card; border: 1px solid $border; border-radius: 10px; }
QLabel { color: $text; }
QLabel#title { color: $text_muted; font-size: 12px; }
QLabel#dirBadge {
    background: $badge_bg; color: $badge_text; border-radius: 6px;
    padding: 2px 10px; font-weight: bold; font-size: 13px;
}
QTextEdit {
    background: $view_bg; color: $text; border: 1px solid $border; border-radius: 8px;
    padding: 8px; font-size: 14px;
    selection-background-color: $selection_bg; selection-color: $selection_text;
}
QPushButton {
    background: $secondary_btn; color: $secondary_btn_text; border: none; border-radius: 7px;
    padding: 6px 16px; font-size: 13px;
}
QPushButton:hover { background: $secondary_btn_hover; }
QPushButton:pressed { background: $secondary_btn_pressed; }
QPushButton#copyBtn { background: $accent; color: $on_accent; }
QPushButton#copyBtn:hover { background: $accent_hover; }
QPushButton#closeBtn { background: $secondary_btn; color: $secondary_btn_text; }
QPushButton#closeBtn:hover { background: $danger; color: $on_accent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border_strong; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: $accent; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""


TRAY_QSS = """
QMenu {
    background-color: $surface;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 8px;
    padding: 6px 4px;
    font-size: 13px;
}
QMenu::item {
    background: transparent;
    color: $text;
    padding: 7px 28px 7px 14px;
    margin: 2px 6px;
    border-radius: 6px;
}
QMenu::item:selected {
    background: $selection_bg;
    color: $selection_text;
}
QMenu::item:disabled {
    color: $disabled_text;
    background: transparent;
}
QMenu::item:disabled:selected {
    background: transparent;
    color: $disabled_text;
}
QMenu::separator {
    height: 1px;
    background: $border_strong;
    margin: 5px 10px;
}
QMenu::indicator {
    width: 15px;
    height: 15px;
    margin-left: 6px;
    border: 1px solid $border_strong;
    border-radius: 4px;
    background: $input_bg;
}
QMenu::indicator:hover {
    border-color: $accent;
}
QMenu::indicator:checked {
    border: 1px solid $accent;
    background: $accent;
}
QMenu::right-arrow {
    width: 8px;
    height: 8px;
}
"""


def app_stylesheet(pal: dict | None = None) -> str:
    return Template(APP_QSS).substitute(pal or current_palette())


def floating_stylesheet(pal: dict | None = None) -> str:
    return Template(FLOATING_QSS).substitute(pal or current_palette())


def tray_menu_stylesheet(pal: dict | None = None) -> str:
    return Template(TRAY_QSS).substitute(pal or current_palette())


class ThemeManager(QObject):
    changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._scheme = resolve_scheme()
        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._on_system_changed)
        except Exception:
            pass

    def _on_system_changed(self, scheme) -> None:
        new_scheme = resolve_scheme()
        if new_scheme != self._scheme:
            log.info("系统主题变化: %s -> %s", self._scheme, new_scheme)
            self._scheme = new_scheme
            if config.get("theme", "system") == "system":
                self.changed.emit(new_scheme)

    def preference(self) -> str:
        return config.get("theme", "system")

    def set_preference(self, value: str) -> None:
        config.set_key("theme", value)
        self._scheme = resolve_scheme()
        self.changed.emit(self._scheme)

    def apply(self) -> None:
        self._scheme = resolve_scheme()
        self.changed.emit(self._scheme)


_manager: ThemeManager | None = None


def manager() -> ThemeManager:
    global _manager
    if _manager is None:
        _manager = ThemeManager()
    return _manager


def apply_to_application() -> None:
    pal = PALETTES[resolve_scheme()]
    QGuiApplication.instance().setPalette(build_qpalette(pal))
