import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from app.core.translator import (
    split_text_into_chunks,
    split_paragraphs_into_chunks,
    rejoin_translated_chunks,
    translate_sync,
    TextChunk,
)
from app.core.glossary import Glossary


class MockLlamaServer:
    def __init__(self, mode="normal"):
        self.mode = mode
        self.call_count = 0
        self.prompts = []
        self.max_tokens_list = []
        self.last_finish_reason = "stop"

    def chat(self, prompt: str, max_tokens: int | None = None, timeout: float = 600.0) -> str:
        self.call_count += 1
        self.prompts.append(prompt)
        self.max_tokens_list.append(max_tokens)

        # Simulate truncation on first call if mode is 'length_truncation'
        if self.mode == "length_truncation" and self.call_count == 1:
            self.last_finish_reason = "length"
            return "This was truncated..."
        
        self.last_finish_reason = "stop"

        # Extract the source text from the prompt (it appears after the last double newline)
        lines = prompt.split("\n\n")
        text = lines[-1] if len(lines) > 1 else prompt
        
        # Simple simulated translation: prefix with [T: ...]
        return f"译文: {text}"


def test_chunking_no_newlines():
    print("--- Test 1: Long text without newlines (3500 chars) ---")
    text = "This is a sentence in a very long paragraph without line breaks. " * 50
    assert len(text) > 3000
    assert "\n" not in text

    chunks = split_text_into_chunks(text, max_chars=1000)
    print(f"Split {len(text)} chars into {len(chunks)} chunks")
    assert len(chunks) >= 4
    for i, c in enumerate(chunks):
        assert len(c.text) <= 1000, f"Chunk {i} exceeded max_chars: {len(c.text)}"
    
    # Verify backward compat function also handles it
    compat_chunks = split_paragraphs_into_chunks(text, max_chars=1000)
    assert len(compat_chunks) >= 4
    for c in compat_chunks:
        assert len(c) <= 1000


def test_chunking_mixed_document():
    print("--- Test 2: Mixed document with headings, long paragraphs, lists ---")
    doc = (
        "# Title\n\n"
        "Short paragraph 1.\n\n"
        "Very long paragraph. " + ("Sentence in paragraph. " * 50) + "End of long paragraph.\n\n"
        "- Item 1\n"
        "- Item 2\n\n"
        "Final paragraph."
    )
    chunks = split_text_into_chunks(doc, max_chars=800)
    print(f"Doc length: {len(doc)}, Chunks: {len(chunks)}")
    for i, c in enumerate(chunks):
        assert len(c.text) <= 800, f"Chunk {i} exceeded: {len(c.text)}"
    
    # Reassembly of original text must be 100% exact
    reconstructed = "".join(c.text + c.separator for c in chunks)
    assert reconstructed == doc


def test_translate_sync_long_text():
    print("--- Test 3: translate_sync with mock server & progress callback ---")
    server = MockLlamaServer()
    text = (
        "第一段内容，用于测试段落结构。\n\n"
        "第二段内容是一个非常长的段落。" + ("这是一个很长的中文句子，用于验证句子拆分与重组。" * 40) + "长段落结束。\n\n"
        "第三段内容是结尾。"
    )
    progress_records = []
    
    def on_progress(cur, tot):
        progress_records.append((cur, tot))

    result = translate_sync(server, text, forced_dir="zh2en", progress_callback=on_progress)
    
    print(f"Translated in {server.call_count} server calls")
    assert server.call_count > 1
    assert len(progress_records) == server.call_count
    assert progress_records[-1] == (server.call_count, server.call_count)
    assert result["src_lang"] == "zh"
    assert result["tgt_lang"] == "en"
    assert "\n\n" in result["result"]
    print("Structure preserved in result!")


def test_direction_consistency():
    print("--- Test 4: Direction consistency across chunks ---")
    server = MockLlamaServer()
    # Chinese document with a chunk that contains only English characters / code / numbers
    chunk1 = "这是中文的第一部分内容，讲述系统的核心功能与设计理念。" * 15
    chunk2 = "function calculateTotal(items) { return items.reduce((a, b) => a + b.price, 0); } " * 12
    chunk3 = "这是中文的第三部分内容，总结测试结果。" * 15
    full_doc = f"{chunk1}\n\n{chunk2}\n\n{chunk3}"

    result = translate_sync(server, full_doc, forced_dir=None)
    assert result["src_lang"] == "zh"
    assert result["tgt_lang"] == "en"
    # Verify all server calls received '英语' in the prompt (not 'Chinese')
    for p in server.prompts:
        assert "英语" in p, "Language direction flipped in a chunk!"
    print("Direction remained strictly 'zh -> en' for all chunks!")


def test_length_truncation_recovery():
    print("--- Test 5: Length truncation recovery ---")
    server = MockLlamaServer(mode="length_truncation")
    long_para = "This is a sentence in a paragraph. " * 30
    result = translate_sync(server, long_para, forced_dir="en2zh")
    assert result["result"]
    assert "This was truncated..." not in result["result"]
    print("Successfully recovered from token truncation!")


def test_huge_document_60k_chars():
    print("--- Test 6: 60,000 characters document chunking ---")
    unit = "这是一段标准中文测试文本，用于模拟用户导入超长小说或文档进行离线翻译。" * 15 + "\n\n"
    huge_text = unit * 100
    assert len(huge_text) >= 50000
    print(f"Generated text length: {len(huge_text)}")
    chunks = split_text_into_chunks(huge_text, max_chars=1000)
    print(f"Doc split into {len(chunks)} chunks")
    assert len(chunks) > 40
    for c in chunks:
        assert len(c.text) <= 1000
    reconstructed = "".join(c.text + c.separator for c in chunks)
    assert reconstructed == huge_text
    print("Doc split and reconstruction 100% exact!")


if __name__ == "__main__":
    test_chunking_no_newlines()
    test_chunking_mixed_document()
    test_translate_sync_long_text()
    test_direction_consistency()
    test_length_truncation_recovery()
    test_huge_document_60k_chars()
    print("\nALL LONG TEXT TRANSLATION TESTS PASSED SUCCESSFULLY!")
