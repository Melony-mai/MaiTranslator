import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from app.core.textguard import protect, restore, postprocess
from app.core.langdetect import detect_language, direction
from app.core.translator import build_prompt

src = """# 项目说明
请访问 https://example.com/docs 或联系 admin@test.com。
代码如下：
```python
print('hello 世界')
```
2023年营收增长 45%，成本 1,234.56 元。见 <b>附录</b> 与 [文档](https://x.cn/a)。"""

lang = detect_language(src)
assert lang == "zh", lang
print("detect:", lang)
pt = protect(src, protect_numbers=True)
print("--- protected ---")
print(pt.protected_text)
assert "https://example.com/docs" not in pt.protected_text
assert "admin@test.com" not in pt.protected_text
assert "print('hello" not in pt.protected_text
assert "2023" not in pt.protected_text
print("segments:", len(pt.segments))

fake = pt.protected_text.replace("项目说明", "Project Overview")
fake = fake.replace("请访问", "Please visit").replace("或联系", "or contact")
fake = fake.replace("代码如下", "The code is as follows")
restored = restore(fake, pt)
print("--- restored ---")
print(restored)
for token in [
    "https://example.com/docs",
    "admin@test.com",
    "print('hello 世界')",
    "2023",
    "45%",
    "1,234.56",
    "<b>",
    "[文档](https://x.cn/a)",
]:
    assert token in restored, f"missing: {token}"
print("restore OK")

en = "The quick brown fox jumps over 42 lazy dogs in 2023."
assert detect_language(en) == "en"
assert direction(en) == ("en", "zh")
assert direction(src) == ("zh", "en")
print("direction OK")

p1 = build_prompt("你好世界", "zh", "en", None)
assert "英语" in p1 and "你好世界" in p1
p2 = build_prompt("hello world", "en", "zh", [{"term": "OpenAI", "translation": "开放人工智能"}])
assert "Chinese" in p2 and "OpenAI" in p2 and "开放人工智能" in p2
p3 = build_prompt("术语测试", "zh", "en", [{"term": "大模型", "translation": "LLM"}])
assert "大模型 翻译成 LLM" in p3
print("prompt OK")

out = postprocess('"Hello World"', '"quoted source"')
assert out == '"Hello World"', out
out2 = postprocess('"Hello World"', "plain source")
assert out2 == "Hello World", out2
out3 = postprocess("译文：你好", "hi")
assert out3 == "你好"
print("postprocess OK")

from app.core.history import History
import tempfile, os
os.environ["APPDATA"] = tempfile.mkdtemp()
import importlib
import app.core.paths as paths
importlib.reload(paths)
import app.core.config as config
config.reset_cache_for_tests()
import app.core.history as history_mod
importlib.reload(history_mod)
h = history_mod.History()
i1 = h.add("zh", "en", "测试一", "Test one", 123.4)
i2 = h.add("en", "zh", "Test two", "测试二", 55.0)
assert h.count() == 2
rows = h.query("test")
assert len(rows) == 2
found = h.query("测试二")
assert len(found) == 1 and found[0]["id"] == i2
h.delete([i1])
assert h.count() == 1
h.clear()
assert h.count() == 0
print("history OK")

gdir = os.environ["APPDATA"]
import app.core.glossary as glossary_mod
importlib.reload(glossary_mod)
g = glossary_mod.Glossary()
g.add("大模型", "LLM")
g.add("大模型", "Large Language Model")
assert len(g.pairs) == 1 and g.pairs[0]["translation"] == "Large Language Model"
hits = g.matching_pairs("这个大模型很强")
assert hits and hits[0]["term"] == "大模型"
print("glossary OK")

print("ALL CORE TESTS PASSED")
