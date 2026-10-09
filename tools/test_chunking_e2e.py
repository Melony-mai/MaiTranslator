import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from app.core.translator import split_paragraphs_into_chunks

# Test 1: Short text should not be chunked
short = "这是一个简短的句子。"
assert split_paragraphs_into_chunks(short, max_chars=1200) == [short]

# Test 2: Multi-paragraph long text
para1 = "这是第一段内容。" * 50 # 400 chars
para2 = "这是第二段内容。" * 50 # 400 chars
para3 = "这是第三段内容。" * 50 # 400 chars
para4 = "这是第四段内容。" * 50 # 400 chars
para5 = "这是第五段内容。" * 50 # 400 chars

full_doc = f"{para1}\n\n{para2}\n\n{para3}\n\n{para4}\n\n{para5}"
assert len(full_doc) >= 2000, len(full_doc)

chunks = split_paragraphs_into_chunks(full_doc, max_chars=1000)
assert len(chunks) > 1
print(f"Split {len(full_doc)} chars into {len(chunks)} chunks:")
for i, c in enumerate(chunks):
    print(f"  Chunk {i}: {len(c)} chars")
    assert len(c) <= 1000

# Re-joined should preserve text
rejoined = "\n".join(chunks)
assert rejoined == full_doc
print("Chunking preserves exact document structure!")

print("ALL CHUNKING TESTS PASSED")
