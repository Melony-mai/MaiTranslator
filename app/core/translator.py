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
    failed = Signal(str, str)

    def __init__(
        self,
        server: LlamaServer,
        text: str,
        forced_dir: str | None = None,
        glossary: Glossary | None = None,
        parent: QObject | None = None,
        origin: str = "",
    ) -> None:
        super().__init__(parent)
        self._server = server
        self._text = text
        self._forced_dir = forced_dir
        self._glossary = glossary
        self._origin = origin

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
            result["origin"] = self._origin
            self.finished_ok.emit(result)
        except Exception as e:
            log.exception("翻译失败")
            self.failed.emit(str(e), self._origin)


def split_paragraphs_into_chunks(text: str, max_chars: int = 1200) -> list[str]:
    lines = text.split("\n")
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > max_chars and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_len = line_len
        else:
            current_chunk.append(line)
            current_len += line_len
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    return chunks


def _translate_chunk_sync(
    server: LlamaServer,
    text: str,
    forced_dir: str | None = None,
    glossary: Glossary | None = None,
) -> dict:
    src, tgt = langdetect.direction(text, forced_dir)
    protect_numbers = bool(config.get("protect_numbers", True))
    pt = protect(text, protect_numbers=protect_numbers)

    pairs = []
    if glossary is not None:
        pairs = glossary.matching_pairs(pt.protected_text) or glossary.matching_pairs(text)

    prompt = build_prompt(pt.protected_text, src, tgt, pairs or None)
    prompt_chars = len(prompt)
    est_tokens = max(256, int(prompt_chars * 1.6))
    ctx = int(config.get("context", 4096))
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


def translate_sync(
    server: LlamaServer,
    text: str,
    forced_dir: str | None = None,
    glossary: Glossary | None = None,
) -> dict:
    text = text.strip("\ufeff").strip()
    if not text:
        raise ValueError("没有可翻译的文本")

    # 长文本按段落分块翻译，避免超出精简上下文并节省显存
    if len(text) > 1500 and "\n" in text:
        chunks = split_paragraphs_into_chunks(text, max_chars=1200)
        if len(chunks) > 1:
            all_results = []
            all_used_terms: set[str] = set()
            all_missing_terms: set[str] = set()
            src_lang, tgt_lang = "", ""
            for chunk in chunks:
                if not chunk.strip():
                    all_results.append("")
                    continue
                r = _translate_chunk_sync(server, chunk, forced_dir, glossary)
                all_results.append(r["result"])
                all_used_terms.update(r["used_terms"])
                all_missing_terms.update(r["missing_terms"])
                src_lang = r["src_lang"]
                tgt_lang = r["tgt_lang"]
            return {
                "source": text,
                "result": "\n".join(all_results),
                "src_lang": src_lang,
                "tgt_lang": tgt_lang,
                "used_terms": sorted(all_used_terms),
                "missing_terms": sorted(all_missing_terms - all_used_terms),
            }

    return _translate_chunk_sync(server, text, forced_dir, glossary)


class TranslationService(QObject):
    finished_ok = Signal(dict)
    failed = Signal(str, str)
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
        self._queued: tuple[str, str | None, str] | None = None
        self.server.stateChanged.connect(self._on_server_state_changed)

    @property
    def busy(self) -> bool:
        if self._queued is not None:
            return True
        return self._worker is not None and self._worker.isRunning()

    def submit(self, text: str, forced_dir: str | None = None, origin: str = "") -> bool:
        if self.busy:
            log.info("已有翻译任务进行中，忽略新请求")
            return False
        if self.server.state == LlamaServer.STATE_ERROR:
            detail = self.server._error_msg or "请到设置页查看引擎状态"
            self.failed.emit(f"推理引擎异常：{detail}", origin)
            return False
        status = self.server.ensure_ready_async()
        if status == "unavailable":
            self.failed.emit("推理引擎尚未就绪，无法启动。请在设置页检查引擎与模型。", origin)
            return False
        if status == "ready":
            self.busy_changed.emit(True)
            self._dispatch(text, forced_dir, origin)
            return True
        log.info("引擎需要加载资源，翻译请求已排队等待就绪（%s）", status)
        self._queued = (text, forced_dir, origin)
        self.server.pending_requests += 1
        self.busy_changed.emit(True)
        if self.server.state == LlamaServer.STATE_READY:
            self._dequeue_dispatch()
        return True

    def _dispatch(self, text: str, forced_dir: str | None, origin: str) -> None:
        self.server.mark_activity()
        worker = TranslationWorker(self.server, text, forced_dir, self.glossary, origin=origin)
        worker.finished_ok.connect(self._on_done)
        worker.failed.connect(self._on_fail)
        worker.finished.connect(self._cleanup)
        self._worker = worker
        worker.start()

    def _take_queued(self) -> tuple[str, str | None, str] | None:
        queued = self._queued
        self._queued = None
        if queued is not None:
            self.server.pending_requests = max(0, self.server.pending_requests - 1)
        return queued

    def _dequeue_dispatch(self) -> None:
        queued = self._take_queued()
        if queued is not None:
            self._dispatch(*queued)

    def _on_server_state_changed(self, state: str, message: str) -> None:
        if self._queued is None:
            return
        if state == LlamaServer.STATE_READY:
            self._dequeue_dispatch()
        elif state in (LlamaServer.STATE_ERROR, LlamaServer.STATE_STOPPED):
            queued = self._take_queued()
            if queued is not None:
                self.busy_changed.emit(False)
                reason = "推理引擎启动失败" if state == LlamaServer.STATE_ERROR else "推理引擎已停止"
                detail = f"：{message}" if message else ""
                self.failed.emit(f"{reason}{detail}", queued[2])

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

    def _on_fail(self, message: str, origin: str = "") -> None:
        self.failed.emit(message, origin)

    def _cleanup(self) -> None:
        w = self._worker
        self._worker = None
        if w is not None:
            w.deleteLater()
        self.busy_changed.emit(False)
