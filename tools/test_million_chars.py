import io
import os
import sys
import tempfile
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from app.core.translator import (
    split_text_into_chunks,
    rejoin_translated_chunks,
    translate_sync,
    TextChunk,
)
from app.core.textguard import protect, restore
from app.core.history import History


class MockStreamServer:
    def __init__(self):
        self.call_count = 0
        self.last_finish_reason = "stop"

    def chat(self, prompt: str, max_tokens: int | None = None, timeout: float = 600.0) -> str:
        self.call_count += 1
        for marker in ["不要额外解释：\n\n", "without additional explanation.\n\n"]:
            if marker in prompt:
                text = prompt.split(marker, 1)[1]
                break
        else:
            text = prompt
        return f"Translated: {text}"


def test_million_char_chunking_and_rejoining():
    print("--- Test 1: Chunking & Rejoining 1,000,000 characters ---")
    unit = "这是一个用于测试超大规模长文档翻译的段落。包含多句话，用来验证性能与准确性！\n\n"
    # Create 1M characters
    repeats = 1_000_000 // len(unit) + 10
    huge_doc = unit * repeats
    assert len(huge_doc) >= 1_000_000
    print(f"Generated test document: {len(huge_doc):,} characters")

    t0 = time.monotonic()
    chunks = split_text_into_chunks(huge_doc, max_chars=1500)
    t1 = time.monotonic()
    print(f"Splitting 1M chars took {t1 - t0:.3f}s, created {len(chunks)} chunks")
    assert len(chunks) > 500
    assert all(len(c.text) <= 1500 for c in chunks)

    # Verify exact reconstruction
    t0 = time.monotonic()
    reconstructed = "".join(c.text + c.separator for c in chunks)
    t1 = time.monotonic()
    print(f"Reconstruction took {t1 - t0:.3f}s")
    assert reconstructed == huge_doc
    print("Exact 1M-char reconstruction passed!")


def test_million_char_textguard_restore():
    print("--- Test 2: Textguard $O(N)$ protect & restore on 1,000,000 characters ---")
    line = "项目数据在 2024 年达到 99.8%，详见 https://example.com/data。\n"
    huge_text = line * 25000
    assert len(huge_text) >= 1_000_000
    print(f"Protecting {len(huge_text):,} characters with thousands of numbers & URLs...")

    t0 = time.monotonic()
    pt = protect(huge_text, protect_numbers=True)
    t1 = time.monotonic()
    print(f"Protect took {t1 - t0:.3f}s, generated {len(pt.segments):,} placeholders")
    assert len(pt.segments) >= 36000

    t0 = time.monotonic()
    restored = restore(pt.protected_text, pt)
    t1 = time.monotonic()
    print(f"Fast restore on {len(pt.segments):,} placeholders took {t1 - t0:.3f}s")
    assert restored == huge_text
    assert t1 - t0 < 1.0, f"Restore was too slow: {t1 - t0:.2f}s"
    print("1M-char textguard performance verified!")


def test_million_char_streaming_translation():
    print("--- Test 3: Streaming chunk translation for large document ---")
    server = MockStreamServer()
    # 50,000 characters test to simulate multi-segment stream
    unit = "深度学习与大模型技术的发展正在彻底改变跨语言沟通的范式。" * 10 + "\n\n"
    doc = unit * 100
    print(f"Document length: {len(doc):,} characters")

    streamed_records = []
    def chunk_cb(partial_text, cur, tot):
        streamed_records.append((len(partial_text), cur, tot))

    result = translate_sync(server, doc, forced_dir="zh2en", chunk_callback=chunk_cb, chunk_size=1500)

    print(f"Translation completed in {server.call_count} chunks")
    assert len(streamed_records) == server.call_count
    # Verify stream length grew monotonically
    for i in range(1, len(streamed_records)):
        assert streamed_records[i][0] >= streamed_records[i - 1][0]
    
    assert len(result["result"]) >= len(doc)
    print(f"Final translated output length: {len(result['result']):,} characters")
    print("Streaming generation passed!")


def test_history_copy_full_text():
    print("--- Test 4: History stores and copies full large text without truncation ---")
    tmp_dir = tempfile.mkdtemp()
    os.environ["APPDATA"] = tmp_dir
    import importlib
    import app.core.paths as paths
    importlib.reload(paths)
    import app.core.history as hist_mod
    importlib.reload(hist_mod)
    
    h = hist_mod.History()
    large_source = "Source " * 20000 # ~140,000 chars
    large_result = "Result " * 20000 # ~140,000 chars
    rec_id = h.add("en", "zh", large_source, large_result, 1200.0)

    rec = h.get(rec_id)
    assert rec is not None
    assert len(rec["source"]) == len(large_source)
    assert len(rec["result"]) == len(large_result)
    print(f"Stored and retrieved full {len(rec['result']):,} characters from history successfully!")


if __name__ == "__main__":
    test_million_char_chunking_and_rejoining()
    test_million_char_textguard_restore()
    test_million_char_streaming_translation()
    test_history_copy_full_text()
    print("\nALL 1M-CHARACTER OUTPUT TESTS PASSED SUCCESSFULLY!")
