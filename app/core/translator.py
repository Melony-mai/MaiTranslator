import logging
import re
import time
from dataclasses import dataclass
from typing import Callable

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


@dataclass
class TextChunk:
    text: str
    separator: str = ""


_SENTENCE_BOUNDARY_RE = re.compile(
    r'([。！？；…]+[”’」』）】"\']?'
    r'|(?<=[.!?])\s+(?=[A-Z0-9"\'“‘\u4e00-\u9fa5])'
    r'|;\s+)'
)

_CLAUSE_BOUNDARY_RE = re.compile(r'([，、：,:\t]+|\s+)')


def split_long_line_to_sublines(line: str, max_chars: int = 1000) -> list[str]:
    """Splits a single line or paragraph that exceeds max_chars into sublines <= max_chars."""
    if len(line) <= max_chars:
        return [line]

    tokens = _SENTENCE_BOUNDARY_RE.split(line)
    sentences: list[str] = []
    for i in range(0, len(tokens) - 1, 2):
        s = tokens[i] + tokens[i + 1]
        if s:
            sentences.append(s)
    if tokens and tokens[-1]:
        sentences.append(tokens[-1])

    fine_units: list[str] = []
    for s in sentences:
        if len(s) <= max_chars:
            fine_units.append(s)
            continue
        ctokens = _CLAUSE_BOUNDARY_RE.split(s)
        c_parts: list[str] = []
        for k in range(0, len(ctokens) - 1, 2):
            cchunk = ctokens[k] + ctokens[k + 1]
            if cchunk:
                c_parts.append(cchunk)
        if ctokens and ctokens[-1]:
            c_parts.append(ctokens[-1])
        for cp in c_parts:
            if len(cp) <= max_chars:
                fine_units.append(cp)
            else:
                for idx in range(0, len(cp), max_chars):
                    fine_units.append(cp[idx : idx + max_chars])

    sublines: list[str] = []
    curr = ""
    for u in fine_units:
        if curr and len(curr) + len(u) > max_chars:
            sublines.append(curr)
            curr = u
        else:
            curr += u
    if curr:
        sublines.append(curr)
    return sublines


def split_paragraphs_into_chunks(text: str, max_chars: int = 1200) -> list[str]:
    """Splits text into chunks <= max_chars while preserving paragraph breaks.
    Backward-compatible with original API and test expectations.
    """
    lines = text.split("\n")
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_len = 0
    for line in lines:
        if len(line) > max_chars:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_len = 0
            sub_lines = split_long_line_to_sublines(line, max_chars)
            for sub in sub_lines[:-1]:
                chunks.append(sub)
            current_chunk = [sub_lines[-1]]
            current_len = len(sub_lines[-1]) + 1
            continue

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


def split_text_into_chunks(text: str, max_chars: int = 1000) -> list[TextChunk]:
    """Splits text into semantically cohesive chunks <= max_chars.
    Preserves exact paragraph delimiters and tracks intra-paragraph sentence splits
    so that rejoining translated chunks perfectly preserves document layout.
    """
    if not text:
        return []
    if len(text) <= max_chars:
        return [TextChunk(text=text, separator="")]

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    para_pattern = re.compile(r'(\n+)')
    tokens = para_pattern.split(normalized)

    raw_blocks: list[tuple[str, str]] = []
    for i in range(0, len(tokens) - 1, 2):
        raw_blocks.append((tokens[i], tokens[i + 1]))
    if tokens and tokens[-1]:
        raw_blocks.append((tokens[-1], ""))

    units: list[tuple[str, str]] = []

    for content, sep in raw_blocks:
        if not content:
            if sep:
                if units:
                    prev_text, prev_sep = units[-1]
                    units[-1] = (prev_text, prev_sep + sep)
                else:
                    units.append(("", sep))
            continue

        if len(content) <= max_chars:
            units.append((content, sep))
            continue

        sub_parts = split_long_line_to_sublines(content, max_chars)
        for idx, sub in enumerate(sub_parts):
            is_last = (idx == len(sub_parts) - 1)
            units.append((sub, sep if is_last else ""))

    chunks: list[TextChunk] = []
    curr_text = ""
    curr_sep = ""

    for utext, usep in units:
        if not utext and not curr_text:
            curr_sep += usep
            continue

        joiner = curr_sep
        needed = len(curr_text) + len(joiner) + len(utext)
        if curr_text and needed > max_chars:
            chunks.append(TextChunk(text=curr_text, separator=curr_sep))
            curr_text = utext
            curr_sep = usep
        else:
            if curr_text:
                curr_text = curr_text + joiner + utext
            else:
                curr_text = utext
            curr_sep = usep

    if curr_text or curr_sep:
        chunks.append(TextChunk(text=curr_text, separator=curr_sep))

    return chunks


def rejoin_translated_chunks(translations: list[str], chunks: list[TextChunk], tgt_lang: str) -> str:
    """Reassembles translated chunks respecting original separators."""
    parts: list[str] = []
    for i, (t, chunk) in enumerate(zip(translations, chunks)):
        parts.append(t)
        if i == len(chunks) - 1:
            break
        sep = chunk.separator
        if "\n" in sep:
            parts.append(sep)
        else:
            if tgt_lang == "en":
                if t and not t[-1].isspace() and i + 1 < len(translations) and translations[i + 1] and not translations[i + 1][0].isspace():
                    parts.append(" ")
            else:
                if t and t[-1].isascii() and t[-1].isalnum() and i + 1 < len(translations) and translations[i + 1] and translations[i + 1][0].isascii() and translations[i + 1][0].isalnum():
                    parts.append(" ")
    return "".join(parts)


class TranslationWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str, str)
    progress = Signal(int, int)
    chunk_translated = Signal(str, int, int)

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
                progress_callback=lambda cur, tot: self.progress.emit(cur, tot),
                chunk_callback=lambda partial, cur, tot: self.chunk_translated.emit(partial, cur, tot),
            )
            duration_ms = (time.monotonic() - started) * 1000.0
            result["duration_ms"] = round(duration_ms, 1)
            result["origin"] = self._origin
            self.finished_ok.emit(result)
        except Exception as e:
            log.exception("翻译失败")
            self.failed.emit(str(e), self._origin)


def _translate_chunk_sync(
    server: LlamaServer,
    text: str,
    src: str | None = None,
    tgt: str | None = None,
    forced_dir: str | None = None,
    glossary: Glossary | None = None,
) -> dict:
    if not text.strip():
        return {
            "source": text,
            "result": text,
            "src_lang": src or "zh",
            "tgt_lang": tgt or "en",
            "used_terms": [],
            "missing_terms": [],
        }

    if src is None or tgt is None:
        src, tgt = langdetect.direction(text, forced_dir)

    protect_numbers = bool(config.get("protect_numbers", True))
    pt = protect(text, protect_numbers=protect_numbers)

    pairs = []
    if glossary is not None:
        pairs = glossary.matching_pairs(pt.protected_text) or glossary.matching_pairs(text)

    prompt = build_prompt(pt.protected_text, src, tgt, pairs or None)
    prompt_chars = len(prompt)
    mult = 1.3 if src == "zh" else 0.5
    est_tokens = max(128, int(prompt_chars * mult) + 64)
    ctx = int(config.get("context", 4096))
    available = max(512, ctx - est_tokens - 64)
    budget = min(int(config.get("max_tokens", 4096)), available)

    raw = ""
    for attempt in range(2):
        try:
            raw = server.chat(prompt, max_tokens=budget)
            break
        except Exception as e:
            if attempt == 1:
                raise
            log.warning("分块翻译重试中 (尝试 %d): %s", attempt + 1, e)
            time.sleep(0.5)

    last_fr = getattr(server, "last_finish_reason", None)
    if last_fr == "length" and len(text) > 100:
        log.warning("检测到模型输出因 token 预算耗尽而被截断，正在细分重译当前块...")
        sub_chunks = split_text_into_chunks(text, max_chars=max(100, len(text) // 2))
        if len(sub_chunks) > 1:
            sub_res = []
            for sc in sub_chunks:
                sr = _translate_chunk_sync(server, sc.text, src, tgt, forced_dir, glossary)
                sub_res.append(sr["result"])
            joined = rejoin_translated_chunks(sub_res, sub_chunks, tgt)
            return {
                "source": text,
                "result": joined,
                "src_lang": src,
                "tgt_lang": tgt,
                "used_terms": [p["term"] for p in pairs if p["translation"] and p["translation"].lower() in joined.lower()],
                "missing_terms": [p["term"] for p in pairs if p["translation"] and p["translation"].lower() not in joined.lower()],
            }

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
    progress_callback: Callable[[int, int], None] | None = None,
    chunk_callback: Callable[[str, int, int], None] | None = None,
    chunk_size: int = 1000,
) -> dict:
    text = text.strip("\ufeff").strip()
    if not text:
        raise ValueError("没有可翻译的文本")

    src_lang, tgt_lang = langdetect.direction(text, forced_dir)

    chunks = split_text_into_chunks(text, max_chars=chunk_size)
    if len(chunks) <= 1:
        if progress_callback:
            progress_callback(1, 1)
        res = _translate_chunk_sync(
            server,
            text,
            src=src_lang,
            tgt=tgt_lang,
            forced_dir=forced_dir,
            glossary=glossary,
        )
        if chunk_callback:
            chunk_callback(res["result"], 1, 1)
        return res

    log.info("长文本已分割为 %d 个语义分块进行翻译 (总长度: %d 字符)", len(chunks), len(text))
    all_results = []
    all_used_terms: set[str] = set()
    all_missing_terms: set[str] = set()
    total_chunks = len(chunks)

    for i, chunk in enumerate(chunks):
        if progress_callback:
            progress_callback(i + 1, total_chunks)
        if not chunk.text.strip():
            all_results.append(chunk.text)
        else:
            r = _translate_chunk_sync(
                server,
                chunk.text,
                src=src_lang,
                tgt=tgt_lang,
                forced_dir=forced_dir,
                glossary=glossary,
            )
            all_results.append(r["result"])
            all_used_terms.update(r["used_terms"])
            all_missing_terms.update(r["missing_terms"])

        if chunk_callback:
            partial_rejoined = rejoin_translated_chunks(all_results, chunks[: len(all_results)], tgt_lang)
            chunk_callback(partial_rejoined, i + 1, total_chunks)

    rejoined = rejoin_translated_chunks(all_results, chunks, tgt_lang)
    return {
        "source": text,
        "result": rejoined,
        "src_lang": src_lang,
        "tgt_lang": tgt_lang,
        "used_terms": sorted(all_used_terms),
        "missing_terms": sorted(all_missing_terms - all_used_terms),
    }


class TranslationService(QObject):
    finished_ok = Signal(dict)
    failed = Signal(str, str)
    busy_changed = Signal(bool)
    progress = Signal(int, int, str)
    chunk_translated = Signal(str, int, int, str)

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
        worker.progress.connect(lambda cur, tot, o=origin: self.progress.emit(cur, tot, o))
        worker.chunk_translated.connect(lambda txt, cur, tot, o=origin: self.chunk_translated.emit(txt, cur, tot, o))
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
