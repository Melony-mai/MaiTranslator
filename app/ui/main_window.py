import logging
import os
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core import config
from app.core.engine import LlamaServer
from app.core.glossary import Glossary
from app.core.history import History
from app.core.paths import data_dir, logs_dir
from app.integrations import contextmenu as contextmenu_helper
from app.integrations import startup
from app.ui.theme import app_stylesheet, current_palette, manager as theme_manager

log = logging.getLogger(__name__)

DIRECTION_TEXTS = {
    ("zh", "en"): "中 → 英",
    ("en", "zh"): "英 → 中",
}


class MainWindow(QWidget):
    translate_requested = Signal(str, str)
    copy_clipboard_requested = Signal()

    def __init__(
        self,
        server: LlamaServer,
        glossary: Glossary,
        history: History,
    ) -> None:
        super().__init__(None)
        self.setObjectName("mainWindow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.server = server
        self.glossary = glossary
        self.history = history
        self.setWindowTitle("MaiTranslator · 本地离线翻译")
        self.resize(920, 640)
        self._forced_dir = "auto"
        self._loading_settings = True
        self._build_ui()
        self._load_glossary_table()
        self._refresh_history()
        self._sync_settings_widgets()
        self._loading_settings = False
        theme_manager().changed.connect(self.retheme)
        self.retheme()
        self.update_engine_status(server.state, server._error_msg)

    def retheme(self, *args) -> None:
        pal = current_palette()
        self.setStyleSheet(app_stylesheet(pal))
        self.update_engine_status(self.server.state, self.server._error_msg)
        style = self.style()
        for child in self.findChildren(QWidget):
            style.unpolish(child)
            style.polish(child)
            child.update()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self.tab_translate = QWidget()
        self.tabs.addTab(self.tab_translate, "翻 译")
        self._build_translate_tab()

        self.tab_history = QWidget()
        self.tabs.addTab(self.tab_history, "历史记录")
        self._build_history_tab()

        self.tab_glossary = QWidget()
        self.tabs.addTab(self.tab_glossary, "术语词表")
        self._build_glossary_tab()

        self.tab_settings = QWidget()
        self.tabs.addTab(self.tab_settings, "设 置")
        self._build_settings_tab()

    def _build_translate_tab(self) -> None:
        lay = QVBoxLayout(self.tab_translate)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        top = QHBoxLayout()
        dir_label = QLabel("翻译方向：")
        top.addWidget(dir_label)
        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["自动检测", "中 → 英", "英 → 中"])
        self.dir_combo.currentIndexChanged.connect(self._on_dir_changed)
        top.addWidget(self.dir_combo)
        top.addStretch(1)
        self.detect_label = QLabel("")
        self.detect_label.setObjectName("hint")
        top.addWidget(self.detect_label)
        lay.addLayout(top)

        src_title = QLabel("原文（自动识别中英文）")
        lay.addWidget(src_title)
        self.source_edit = QTextEdit()
        self.source_edit.setPlaceholderText("在此粘贴或输入需要翻译的文本…\n快捷键 Alt + F 可在任意程序中划词翻译。")
        self.source_edit.setMinimumHeight(150)
        lay.addWidget(self.source_edit, stretch=1)

        btn_row = QHBoxLayout()
        self.go_btn = QPushButton("立即翻译 (Ctrl+Return)")
        self.go_btn.clicked.connect(self._on_translate_clicked)
        btn_row.addWidget(self.go_btn)
        clear_btn = QPushButton("清空")
        clear_btn.setProperty("class", "secondary")
        clear_btn.clicked.connect(self._on_clear_clicked)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch(1)
        copy_src_btn = QPushButton("复制原文")
        copy_src_btn.setProperty("class", "secondary")
        copy_src_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.source_edit.toPlainText()))
        btn_row.addWidget(copy_src_btn)
        copy_dst_btn = QPushButton("复制译文")
        copy_dst_btn.clicked.connect(self._copy_result)
        btn_row.addWidget(copy_dst_btn)
        lay.addLayout(btn_row)

        dst_title = QLabel("译文")
        lay.addWidget(dst_title)
        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setMinimumHeight(150)
        self.result_edit.setPlaceholderText("译文将显示在这里，并自动复制到剪贴板。")
        lay.addWidget(self.result_edit, stretch=1)

        self.translate_status = QLabel("")
        self.translate_status.setObjectName("hint")
        lay.addWidget(self.translate_status)

    def _build_history_tab(self) -> None:
        lay = QVBoxLayout(self.tab_history)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        search_row = QHBoxLayout()
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("搜索历史记录（原文或译文关键字）…")
        self.history_search.returnPressed.connect(self._refresh_history)
        search_row.addWidget(self.history_search, stretch=1)
        do_search = QPushButton("搜索")
        do_search.clicked.connect(self._refresh_history)
        search_row.addWidget(do_search)
        reset_btn = QPushButton("显示全部")
        reset_btn.setProperty("class", "secondary")
        reset_btn.clicked.connect(self._show_all_history)
        search_row.addWidget(reset_btn)
        lay.addLayout(search_row)

        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(["时间", "方向", "原文", "译文", "耗时(秒)"])
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.history_table.verticalHeader().setVisible(False)
        lay.addWidget(self.history_table, stretch=1)

        btn_row = QHBoxLayout()
        copy_r = QPushButton("复制译文")
        copy_r.clicked.connect(lambda: self._copy_selected(which="result"))
        btn_row.addWidget(copy_r)
        copy_s = QPushButton("复制原文")
        copy_s.setProperty("class", "secondary")
        copy_s.clicked.connect(lambda: self._copy_selected(which="source"))
        btn_row.addWidget(copy_s)
        btn_row.addStretch(1)
        del_btn = QPushButton("删除所选")
        del_btn.setProperty("class", "secondary")
        del_btn.clicked.connect(self._delete_selected_history)
        btn_row.addWidget(del_btn)
        clr_btn = QPushButton("清空全部")
        clr_btn.setProperty("class", "danger")
        clr_btn.clicked.connect(self._clear_history)
        btn_row.addWidget(clr_btn)
        lay.addLayout(btn_row)

    def _build_glossary_tab(self) -> None:
        lay = QVBoxLayout(self.tab_glossary)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        hint = QLabel(
            "自定义术语将在翻译时优先参考（官方术语干预模板）。"
            "例如：源术语“大模型” → 译法“LLM”。修改后即时保存。"
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.glossary_table = QTableWidget(0, 2)
        self.glossary_table.setHorizontalHeaderLabels(["源术语", "目标译法"])
        self.glossary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.glossary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.glossary_table.verticalHeader().setVisible(False)
        self.glossary_table.itemChanged.connect(self._on_glossary_item_changed)
        lay.addWidget(self.glossary_table, stretch=1)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("添加术语")
        add_btn.clicked.connect(self._add_glossary_row)
        btn_row.addWidget(add_btn)
        del_btn = QPushButton("删除所选")
        del_btn.setProperty("class", "secondary")
        del_btn.clicked.connect(self._delete_glossary_rows)
        btn_row.addWidget(del_btn)
        btn_row.addStretch(1)
        imp_btn = QPushButton("导入 JSON")
        imp_btn.setProperty("class", "secondary")
        imp_btn.clicked.connect(self._import_glossary)
        btn_row.addWidget(imp_btn)
        exp_btn = QPushButton("导出 JSON")
        exp_btn.setProperty("class", "secondary")
        exp_btn.clicked.connect(self._export_glossary)
        btn_row.addWidget(exp_btn)
        lay.addLayout(btn_row)

    def _build_settings_tab(self) -> None:
        scroll_area_holder = QVBoxLayout(self.tab_settings)
        scroll_area_holder.setContentsMargins(0, 0, 0, 0)

        from PySide6.QtWidgets import QScrollArea, QSizePolicy

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        holder.setAutoFillBackground(False)
        area.setWidget(holder)
        scroll_area_holder.addWidget(area)

        lay = QVBoxLayout(holder)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        engine_box = QGroupBox("推理引擎")
        form = QFormLayout(engine_box)
        self.engine_status = QLabel("-")
        form.addRow("当前状态：", self.engine_status)
        eng_btns = QHBoxLayout()
        start_btn = QPushButton("启动引擎")
        start_btn.clicked.connect(self.server.start)
        eng_btns.addWidget(start_btn)
        restart_btn = QPushButton("重启引擎")
        restart_btn.setProperty("class", "secondary")
        restart_btn.clicked.connect(self.server.restart)
        eng_btns.addWidget(restart_btn)
        stop_btn = QPushButton("停止引擎")
        stop_btn.setProperty("class", "danger")
        stop_btn.clicked.connect(self.server.stop)
        eng_btns.addWidget(stop_btn)
        form.addRow("", eng_btns)

        model_row = QHBoxLayout()
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("默认使用内置模型 models\\HY-MT1.5-7B-Q4_K_M.gguf")
        model_row.addWidget(self.model_edit, stretch=1)
        browse = QPushButton("浏览…")
        browse.setProperty("class", "secondary")
        browse.clicked.connect(self._browse_model)
        model_row.addWidget(browse)
        apply_model = QPushButton("应用")
        apply_model.clicked.connect(self._apply_model_path)
        model_row.addWidget(apply_model)
        form.addRow("模型文件：", model_row)

        self.gpu_combo = QComboBox()
        self.gpu_combo.addItem("自动（GPU 优先，失败回退 CPU）", "auto")
        self.gpu_combo.addItem("强制 GPU", "gpu")
        self.gpu_combo.addItem("仅 CPU", "cpu")
        self.gpu_combo.currentIndexChanged.connect(self._save_settings)
        form.addRow("加速模式：", self.gpu_combo)

        self.ctx_combo = QComboBox()
        for v in (2048, 4096, 8192, 16384, 32768):
            self.ctx_combo.addItem(f"{v} tokens", v)
        self.ctx_combo.currentIndexChanged.connect(self._save_settings)
        form.addRow("上下文长度：", self.ctx_combo)

        self.kv_combo = QComboBox()
        self.kv_combo.addItem("f16（最高质量）", "f16")
        self.kv_combo.addItem("q8_0（推荐）", "q8_0")
        self.kv_combo.addItem("q4_0（最省显存）", "q4_0")
        self.kv_combo.currentIndexChanged.connect(self._save_settings)
        form.addRow("KV 缓存精度：", self.kv_combo)

        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 32)
        self.threads_spin.valueChanged.connect(self._save_settings)
        form.addRow("CPU 线程数：", self.threads_spin)
        lay.addWidget(engine_box)

        sample_box = QGroupBox("采样参数（官方推荐值）")
        sform = QFormLayout(sample_box)
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.05)
        self.temp_spin.valueChanged.connect(self._save_settings)
        sform.addRow("temperature：", self.temp_spin)
        self.topk_spin = QSpinBox()
        self.topk_spin.setRange(1, 200)
        self.topk_spin.valueChanged.connect(self._save_settings)
        sform.addRow("top_k：", self.topk_spin)
        self.topp_spin = QDoubleSpinBox()
        self.topp_spin.setRange(0.0, 1.0)
        self.topp_spin.setSingleStep(0.05)
        self.topp_spin.valueChanged.connect(self._save_settings)
        sform.addRow("top_p：", self.topp_spin)
        self.rep_spin = QDoubleSpinBox()
        self.rep_spin.setRange(1.0, 2.0)
        self.rep_spin.setSingleStep(0.01)
        self.rep_spin.valueChanged.connect(self._save_settings)
        sform.addRow("repeat_penalty：", self.rep_spin)
        lay.addWidget(sample_box)

        feat_box = QGroupBox("功能开关")
        fform = QFormLayout(feat_box)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("跟随系统", "system")
        self.theme_combo.addItem("浅色模式", "light")
        self.theme_combo.addItem("深色模式", "dark")
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        fform.addRow("界面主题：", self.theme_combo)
        self.autocopy_check = QCheckBox("翻译完成后自动复制译文到剪贴板")
        self.autocopy_check.stateChanged.connect(self._save_settings)
        fform.addRow(self.autocopy_check)
        self.protectnum_check = QCheckBox("严格保护数字/代码/链接不被改动（推荐开启）")
        self.protectnum_check.stateChanged.connect(self._save_settings)
        fform.addRow(self.protectnum_check)
        self.hotkey_check = QCheckBox("启用全局热键 Alt + F")
        self.hotkey_check.setEnabled(False)
        fform.addRow(self.hotkey_check)
        self.autostart_check = QCheckBox("开机自动启动（最小化到托盘）")
        self.autostart_check.stateChanged.connect(self._on_autostart_toggled)
        fform.addRow(self.autostart_check)
        lay.addWidget(feat_box)

        reset_row = QHBoxLayout()
        reset_btn = QPushButton("恢复默认参数")
        reset_btn.setProperty("class", "secondary")
        reset_btn.clicked.connect(self._restore_defaults)
        reset_row.addWidget(reset_btn)
        reset_hint = QLabel("将推理、采样与功能参数重置为默认值（不影响模型路径与开机自启），引擎将自动重启。")
        reset_hint.setObjectName("hint")
        reset_hint.setWordWrap(True)
        reset_row.addWidget(reset_hint, stretch=1)
        lay.addLayout(reset_row)

        ctx_menu_box = QGroupBox("系统集成")
        cform = QFormLayout(ctx_menu_box)
        self.ctx_status = QLabel("-")
        cform.addRow("右键菜单状态：", self.ctx_status)
        cbtns = QHBoxLayout()
        inst_btn = QPushButton("安装右键菜单")
        inst_btn.clicked.connect(self._install_context_menu)
        cbtns.addWidget(inst_btn)
        uninst_btn = QPushButton("卸载右键菜单")
        uninst_btn.setProperty("class", "secondary")
        uninst_btn.clicked.connect(self._uninstall_context_menu)
        cbtns.addWidget(uninst_btn)
        cform.addRow("", cbtns)
        dbtns = QHBoxLayout()
        log_btn = QPushButton("打开日志文件夹")
        log_btn.setProperty("class", "secondary")
        log_btn.clicked.connect(lambda: os.startfile(str(logs_dir())))
        dbtns.addWidget(log_btn)
        data_btn = QPushButton("打开数据文件夹")
        data_btn.setProperty("class", "secondary")
        data_btn.clicked.connect(lambda: os.startfile(str(data_dir())))
        dbtns.addWidget(data_btn)
        cform.addRow("", dbtns)
        lay.addWidget(ctx_menu_box)

        about = QLabel(
            "MaiTranslator v1.0.0 · 完全离线的本地 AI 翻译器\n"
            "仅使用本地 HY-MT1.5-7B GGUF 模型推理，不连接互联网、不上传任何数据。\n"
            "所有数据（配置、词表、历史、日志）均保存在本机。"
        )
        about.setObjectName("hint")
        lay.addWidget(about)
        lay.addStretch(1)

    def _sync_settings_widgets(self) -> None:
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(config.get("theme", "system"))))
        self.gpu_combo.setCurrentIndex(max(0, self.gpu_combo.findData(config.get("gpu_mode", "auto"))))
        ctx = int(config.get("context", 8192))
        idx = self.ctx_combo.findData(ctx)
        self.ctx_combo.setCurrentIndex(idx if idx >= 0 else 2)
        kv = config.get("kv_cache", "q8_0")
        kidx = self.kv_combo.findData(kv)
        self.kv_combo.setCurrentIndex(kidx if kidx >= 0 else 1)
        self.threads_spin.setValue(int(config.get("threads", 8)))
        self.temp_spin.setValue(float(config.get("temperature", 0.7)))
        self.topk_spin.setValue(int(config.get("top_k", 20)))
        self.topp_spin.setValue(float(config.get("top_p", 0.6)))
        self.rep_spin.setValue(float(config.get("repeat_penalty", 1.05)))
        self.autocopy_check.setChecked(bool(config.get("auto_copy", True)))
        self.protectnum_check.setChecked(bool(config.get("protect_numbers", True)))
        self.hotkey_check.setChecked(bool(config.get("hotkey_enabled", True)))
        self.autostart_check.setChecked(startup.is_enabled())
        self.model_edit.setText(config.get("model_path", "") or "")
        self._refresh_ctx_menu_status()

    def _save_settings(self, *args) -> None:
        if getattr(self, "_loading_settings", False):
            return
        config.set_key("gpu_mode", self.gpu_combo.currentData())
        config.set_key("context", self.ctx_combo.currentData())
        config.set_key("kv_cache", self.kv_combo.currentData())
        config.set_key("threads", self.threads_spin.value())
        config.set_key("temperature", self.temp_spin.value())
        config.set_key("top_k", self.topk_spin.value())
        config.set_key("top_p", self.topp_spin.value())
        config.set_key("repeat_penalty", self.rep_spin.value())
        config.set_key("auto_copy", self.autocopy_check.isChecked())
        config.set_key("protect_numbers", self.protectnum_check.isChecked())

    def _on_theme_changed(self, idx: int) -> None:
        if getattr(self, "_loading_settings", False):
            return
        theme_manager().set_preference(self.theme_combo.currentData())

    RESET_KEEP_KEYS = frozenset({"model_path", "autostart"})

    def _restore_defaults(self) -> None:
        from app.core.config import DEFAULTS

        ret = QMessageBox.question(
            self,
            "MaiTranslator",
            "确定将所有参数恢复为默认值吗？\n\n"
            "· 推理、采样与功能参数将被重置\n"
            "· 模型路径与开机自启设置保持不变\n"
            "· 推理引擎将自动重启",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        for key, value in DEFAULTS.items():
            if key not in self.RESET_KEEP_KEYS:
                config.set_key(key, value)
        self._loading_settings = True
        try:
            self._sync_settings_widgets()
        finally:
            self._loading_settings = False
        theme_manager().apply()
        self.server.restart()
        QMessageBox.information(
            self, "MaiTranslator", "所有参数已恢复为默认值，引擎正在重启。"
        )

    def _on_autostart_toggled(self, state: int) -> None:
        if getattr(self, "_loading_settings", False):
            return
        on = self.autostart_check.isChecked()
        ok = startup.set_enabled(on)
        if not ok:
            self.autostart_check.blockSignals(True)
            self.autostart_check.setChecked(not on)
            self.autostart_check.blockSignals(False)
            QMessageBox.warning(self, "MaiTranslator", "设置开机自启失败，请检查注册表权限。")

    def _browse_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 GGUF 模型文件", str(data_dir()), "GGUF 模型 (*.gguf)"
        )
        if path:
            self.model_edit.setText(path)

    def _apply_model_path(self) -> None:
        config.set_key("model_path", self.model_edit.text().strip())
        QMessageBox.information(
            self, "MaiTranslator", "模型路径已保存。点击“重启引擎”后生效。"
        )

    def _install_context_menu(self) -> None:
        if contextmenu_helper.install():
            QMessageBox.information(self, "MaiTranslator", "右键菜单已安装：右键任意文件即可看到“使用 MaiTranslator 翻译”。")
        else:
            QMessageBox.warning(self, "MaiTranslator", "安装失败，请以普通用户权限重试或查看日志。")
        self._refresh_ctx_menu_status()

    def _uninstall_context_menu(self) -> None:
        if contextmenu_helper.uninstall():
            QMessageBox.information(self, "MaiTranslator", "右键菜单已卸载。")
        self._refresh_ctx_menu_status()

    def _refresh_ctx_menu_status(self) -> None:
        installed = contextmenu_helper.is_installed()
        self.ctx_status.setText("✅ 已安装" if installed else "未安装")

    def update_engine_status(self, state: str, message: str = "") -> None:
        pal = current_palette()
        mapping = {
            LlamaServer.STATE_STOPPED: ("⚪ 已停止", pal["text_muted"]),
            LlamaServer.STATE_LOADING: ("🟡 加载中", pal["warning"]),
            LlamaServer.STATE_READY: ("🟢 就绪", pal["success"]),
            LlamaServer.STATE_ERROR: ("🔴 错误", pal["error"]),
        }
        text, color = mapping.get(state, ("-", pal["text_muted"]))
        extra = f" — {message}" if message and state != LlamaServer.STATE_READY else ""
        self.engine_status.setText(text + extra)
        self.engine_status.setStyleSheet(f"color:{color};")

    def set_translate_busy(self, busy: bool) -> None:
        self.go_btn.setEnabled(not busy)
        if busy:
            self.translate_status.setText("正在本地推理中，请稍候…")
        else:
            self.translate_status.setText("")

    def _on_dir_changed(self, idx: int) -> None:
        self._forced_dir = ["auto", "zh2en", "en2zh"][idx]

    def _on_translate_clicked(self) -> None:
        text = self.source_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "MaiTranslator", "请先输入要翻译的文本。")
            return
        self.result_edit.clear()
        forced = None if self._forced_dir == "auto" else self._forced_dir
        self.translate_requested.emit(text, forced or "")

    def _on_clear_clicked(self) -> None:
        self.source_edit.clear()
        self.result_edit.clear()
        self.translate_status.setText("")

    def show_translation_result(self, result: dict) -> None:
        src, tgt = result["src_lang"], result["tgt_lang"]
        direction_text = DIRECTION_TEXTS.get((src, tgt), f"{src} → {tgt}")
        note_bits = []
        if result.get("used_terms"):
            note_bits.append("词表已生效：" + "、".join(result["used_terms"]))
        secs = result.get("duration_ms", 0) / 1000.0
        self.result_edit.setPlainText(result["result"])
        self.source_edit.setPlainText(result["source"])
        self.translate_status.setText(
            f"{direction_text} · 完成 · {secs:.1f} 秒"
            + ((" · " + "；".join(note_bits)) if note_bits else "")
        )
        self._refresh_history()

    def show_translation_error(self, message: str) -> None:
        self.result_edit.setPlainText("")
        self.translate_status.setText(f"❌ 翻译失败：{message}")

    def _copy_result(self) -> None:
        text = self.result_edit.toPlainText()
        if text:
            QGuiApplication.clipboard().setText(text)

    def load_file_for_translation(self, file_path: str) -> None:
        try:
            raw = open(file_path, "rb").read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("gbk", errors="replace")
            if len(text) > 60000:
                text = text[:60000]
                self.translate_status.setText("文件过长，仅截取前 60000 字符进行翻译。")
            self.tabs.setCurrentIndex(0)
            self.source_edit.setPlainText(text)
            self._on_translate_clicked()
        except OSError as e:
            QMessageBox.warning(self, "MaiTranslator", f"无法读取文件：{e}")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Return and event.modifiers() & Qt.ControlModifier:
            self._on_translate_clicked()
            return
        super().keyPressEvent(event)

    def _show_all_history(self) -> None:
        self.history_search.clear()
        self._refresh_history()

    def _refresh_history(self) -> None:
        search = self.history_search.text().strip() if hasattr(self, "history_search") else ""
        rows = self.history.query(search, limit=300)
        table = self.history_table
        table.setUpdatesEnabled(False)
        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            direction = DIRECTION_TEXTS.get((r["src_lang"], r["tgt_lang"]), f'{r["src_lang"]}→{r["tgt_lang"]}')
            values = [
                r["created_at"],
                direction,
                self._ellipsis(r["source"], 120),
                self._ellipsis(r["result"], 120),
                f'{r["duration_ms"] / 1000.0:.1f}',
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col == 0:
                    item.setData(Qt.UserRole, r["id"])
                if col in (2, 3):
                    item.setToolTip(r["source"] if col == 2 else r["result"])
                table.setItem(i, col, item)
        table.setUpdatesEnabled(True)

    @staticmethod
    def _ellipsis(text: str, n: int) -> str:
        t = text.replace("\n", " ").replace("\r", " ")
        return t if len(t) <= n else t[: n - 1] + "…"

    def _selected_history_ids(self) -> list[int]:
        ids = []
        seen_rows = sorted({it.row() for it in self.history_table.selectedItems()})
        for row in seen_rows:
            id_item = self.history_table.item(row, 0)
            if id_item is not None:
                hid = id_item.data(Qt.UserRole)
                if hid is not None:
                    ids.append(int(hid))
        return ids

    def _copy_selected(self, which: str = "result") -> None:
        col = 3 if which == "result" else 2
        selected_rows = sorted({it.row() for it in self.history_table.selectedItems()})
        texts = []
        for row in selected_rows:
            cell = self.history_table.item(row, col)
            if cell is not None:
                texts.append(cell.text())
        if texts:
            QGuiApplication.clipboard().setText("\n".join(texts))

    def _delete_selected_history(self) -> None:
        ids = self._selected_history_ids()
        if not ids:
            return
        if QMessageBox.question(self, "MaiTranslator", f"确定删除所选的 {len(ids)} 条记录吗？") != QMessageBox.Yes:
            return
        self.history.delete(ids)
        self._refresh_history()

    def _clear_history(self) -> None:
        if QMessageBox.question(self, "MaiTranslator", "确定清空全部历史记录吗？此操作不可恢复。") != QMessageBox.Yes:
            return
        self.history.clear()
        self._refresh_history()

    def _load_glossary_table(self) -> None:
        table = self.glossary_table
        table.blockSignals(True)
        pairs = self.glossary.all_pairs()
        table.setRowCount(len(pairs))
        for i, p in enumerate(pairs):
            table.setItem(i, 0, QTableWidgetItem(p["term"]))
            table.setItem(i, 1, QTableWidgetItem(p["translation"]))
        table.blockSignals(False)

    def _add_glossary_row(self) -> None:
        table = self.glossary_table
        row = table.rowCount()
        table.setRowCount(row + 1)
        table.setItem(row, 0, QTableWidgetItem(""))
        table.setItem(row, 1, QTableWidgetItem(""))
        table.editItem(table.item(row, 0))

    def _delete_glossary_rows(self) -> None:
        rows = sorted({it.row() for it in self.glossary_table.selectedItems()}, reverse=True)
        table = self.glossary_table
        table.blockSignals(True)
        for row in rows:
            table.removeRow(row)
        self._persist_glossary_from_table_locked()
        table.blockSignals(False)

    def _on_glossary_item_changed(self, item) -> None:
        table = self.glossary_table
        table.blockSignals(True)
        self._persist_glossary_from_table_locked()
        table.blockSignals(False)

    def _persist_glossary_from_table_locked(self) -> None:
        table = self.glossary_table
        pairs = []
        for row in range(table.rowCount()):
            a = table.item(row, 0).text() if table.item(row, 0) else ""
            b = table.item(row, 1).text() if table.item(row, 1) else ""
            if a.strip() and b.strip():
                pairs.append({"term": a.strip(), "translation": b.strip()})
        self.glossary.pairs = pairs
        self.glossary.save()

    def _import_glossary(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入词表", str(data_dir()), "JSON (*.json)")
        if not path:
            return
        try:
            count = self.glossary.import_json(path)
            self._load_glossary_table()
            QMessageBox.information(self, "MaiTranslator", f"成功导入 {count} 条术语。")
        except Exception as e:
            QMessageBox.warning(self, "MaiTranslator", f"导入失败：{e}")

    def _export_glossary(self) -> None:
        default = os.path.join(str(data_dir()), f"glossary-{datetime.now():%Y%m%d}.json")
        path, _ = QFileDialog.getSaveFileName(self, "导出词表", default, "JSON (*.json)")
        if not path:
            return
        try:
            self.glossary.export_json(path)
            QMessageBox.information(self, "MaiTranslator", "导出成功。")
        except Exception as e:
            QMessageBox.warning(self, "MaiTranslator", f"导出失败：{e}")
