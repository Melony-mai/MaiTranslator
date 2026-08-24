import logging
import time

from PySide6.QtCore import QObject, QThread, Signal

from . import config, langdetect
from .engine import LlamaServer
from .glossary import Glossary
from .history import History
from .textguard import postprocess, protect, restore

log = logging.getLogger(__name__)

TARGET_NAMES_ZH_TEMPLATE = {"en": "英语"}
TARGET_NAMES_EN_TEMPLATE = {"zh": "Chinese"}


def build_prompt(text: str, src: str, tgt: str, pairs: list[dict[str, str]] | None = None) -> str:
    if src == "zh":
        if pairs:
            term_lines = "\n".join(f"{p['term']} 翻译成 {p['translation']}" for p in pairs)
            return (
                "参考下面的翻译：\n"
                f"{term_lines}\n"
                f"将以下文本翻译为{TARGET_NAMES_ZH_TEMPLATE.get(tgt, tgt)}，"
                "注意只需要输出翻译后的结果，不要额外解释：\n\n"
                f"{text}"
            )
        return (
            f"将以下文本翻译为{TARGET_NAMES_ZH_TEMPLATE.get(tgt, tgt)}，"
            "注意只需要输出翻译后的结果，不要额外解释：\n\n"
            f"{text}"
        )
    else:
        tgt_name = TARGET_NAMES_EN_TEMPLATE.get(tgt, tgt)
        if pairs:
            term_lines = "\n".join(
                f"Take note that {p['term']} should be translated as {p['translation']}"
                for p in pairs
            )
            return (
                f"{term_lines}\n"
                f"Translate the following segment into {tgt_name}, without additional explanation.\n\n"
                f"{text}"
            )
        return (
            f"Translate the following segment into {tgt_name}, without additional explanation.\n\n"
            f"{text}"
        )


class TranslationWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        server: LlamaServer,
        text: str,
        forced_dir: str | None = None,
        glossary: Glossary | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._server = server
        self._text = text
        self._forced_dir = forced_dir
        self._glossary = glossary

    def run(self) -> None:
        started = time.monotonic()
        try:
            result = translate_sync(
                self._server,
                self._text,
                forced_dir=self._forced_dir,
                glossary=self._glossary,
            )
            duration_ms = (time.monotonic() - started) * 1000.0
            result["duration_ms"] = round(duration_ms, 1)
            self.finished_ok.emit(result)
        except Exception as e:
            log.exception("翻译失败")
            self.failed.emit(str(e))


def translate_sync(
    server: LlamaServer,
    text: str,
    forced_dir: str | None = None,
    glossary: Glossary | None = None,
) -> dict:
    text = text.strip("\ufeff").strip()
    if not text:
        raise ValueError("没有可翻译的文本")
    src, tgt = langdetect.direction(text, forced_dir)
    protect_numbers = bool(config.get("protect_numbers", True))
    pt = protect(text, protect_numbers=protect_numbers)

    pairs = []
    if glossary is not None:
        pairs = glossary.matching_pairs(pt.protected_text) or glossary.matching_pairs(text)

    prompt = build_prompt(pt.protected_text, src, tgt, pairs or None)
    prompt_chars = len(prompt)
    est_tokens = max(256, int(prompt_chars * 1.6))
    ctx = int(config.get("context", 8192))
    budget = max(256, min(int(config.get("max_tokens", 4096)), ctx - est_tokens - 64))
    raw = server.chat(prompt, max_tokens=budget)
    restored = restore(raw, pt)
    final = postprocess(restored, text)
    if not final.strip():
        raise RuntimeError("模型未返回有效译文，请重试或调整文本长度")

    used_terms = [p for p in pairs if p["translation"] and p["translation"].lower() in final.lower()]
    missing_terms = [p for p in pairs if p not in used_terms]

    return {
        "source": text,
        "result": final,
        "src_lang": src,
        "tgt_lang": tgt,
        "used_terms": [p["term"] for p in used_terms],
        "missing_terms": [p["term"] for p in missing_terms],
    }


class TranslationService(QObject):
    finished_ok = Signal(dict)
    failed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(
        self,
        server: LlamaServer,
        glossary: Glossary,
        history: History,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.server = server
        self.glossary = glossary
        self.history = history
        self._worker: TranslationWorker | None = None

    @property
    def busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def submit(self, text: str, forced_dir: str | None = None) -> None:
        if self.busy:
            log.info("已有翻译任务进行中，忽略新请求")
            return
        if self.server.state != LlamaServer.STATE_READY:
            self.failed.emit("推理引擎尚未就绪，请稍候或在设置中启动引擎。")
            return
        worker = TranslationWorker(self.server, text, forced_dir, self.glossary)
        worker.finished_ok.connect(self._on_done)
        worker.failed.connect(self._on_fail)
        worker.finished.connect(self._cleanup)
        self._worker = worker
        self.busy_changed.emit(True)
        worker.start()

    def _on_done(self, result: dict) -> None:
        try:
            self.history.add(
                result["src_lang"],
                result["tgt_lang"],
                result["source"],
                result["result"],
                result.get("duration_ms", 0.0),
            )
        except Exception:
            log.exception("历史记录写入失败")
        self.finished_ok.emit(result)

    def _on_fail(self, message: str) -> None:
        self.failed.emit(message)

    def _cleanup(self) -> None:
        w = self._worker
        self._worker = None
        if w is not None:
            w.deleteLater()
        self.busy_changed.emit(False)
