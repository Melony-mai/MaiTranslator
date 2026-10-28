import io
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="maitranslator_long_test_")
print("APPDATA =", os.environ["APPDATA"])

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv[:1])

from app.core import config
from app.core.engine import LlamaServer
from app.core.glossary import Glossary
from app.core.translator import translate_sync

config.set_key("context", 4096)

server = LlamaServer()
glossary = Glossary()

def wait_ready(timeout_s=300.0):
    server.start()
    elapsed = 0.0
    while server.state != LlamaServer.STATE_READY and elapsed < timeout_s:
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        elapsed += 0.1
        if server.state == LlamaServer.STATE_ERROR:
            raise RuntimeError(f"engine error: {server._error_msg}")
    if server.state != LlamaServer.STATE_READY:
        raise RuntimeError("timeout waiting for engine")
    print("ENGINE READY, gpu_active =", server.gpu_active)

wait_ready()

# Test 1: Real translation of a long piece of English text with no newlines (~2,500 chars)
print("\n===== TEST 1: Real English long paragraph (no newlines, ~2500 chars) =====")
en_para = (
    "Artificial intelligence has seen rapid advancements in recent years, transforming various industries across the globe. "
    "Machine translation is one of the most prominent applications of deep learning, allowing people to communicate across language barriers seamlessly. "
    "Traditional statistical methods have largely been replaced by neural network models that capture complex grammatical relationships and nuances. "
    "Recent developments in large language models have further improved translation fluency, contextual understanding, and terminology consistency. "
    "However, translating long documents remains a practical challenge due to hardware memory limits and finite context windows. "
    "Effective chunking strategies allow applications to break down extensive texts into manageable segments without losing coherence. "
    "By dividing text at natural syntactic boundaries, the system ensures that complete thoughts and expressions are preserved during translation. "
    "Furthermore, robust placeholder mechanisms safeguard inline code, web links, numerical figures, and specialized terminology from unwanted alterations. "
    "When translated parts are assembled back together, the overall document retains its intended meaning and natural flow. "
    "This test confirms that long texts can be translated end-to-end by the local neural model without truncation or errors."
)
print("Source length:", len(en_para))

progress_updates = []
def progress_cb(cur, tot):
    print(f"  [Progress] {cur}/{tot}")
    progress_updates.append((cur, tot))

started = time.monotonic()
r1 = translate_sync(server, en_para, forced_dir="en2zh", progress_callback=progress_cb)
duration = time.monotonic() - started

print(f"Translation completed in {duration:.2f}s:")
print(r1["result"])
print("Result length:", len(r1["result"]))
assert r1["src_lang"] == "en" and r1["tgt_lang"] == "zh"
assert len(r1["result"]) >= 400, f"Translation appears truncated! Result len: {len(r1['result'])}"
assert len(progress_updates) >= 2, "Should have been split into at least 2 chunks"
assert "\n" not in r1["result"], "Single paragraph should not have artificial newlines inserted"
print("Test 1 passed successfully!")

# Test 2: Multi-paragraph markdown document (~2,000 chars)
print("\n===== TEST 2: Multi-paragraph markdown document with code & lists =====")
doc = """# 人工智能翻译系统架构

在现代自然语言处理领域中，离线端侧翻译已成为保护用户数据隐私与降低云端依赖的关键方案。通过轻量化模型与高效推理后端的紧密结合，可以在个人计算机上实现高精度、低延迟的文本转换。

系统采用模块化设计理念，划分为以下关键核心层次：
- 核心引擎层：基于本地推理引擎加载轻量级量化模型。
- 文本守护层：识别并保护代码块、网络链接、电子邮箱及专业术语。
- 智能分块层：对长篇文本进行多级语义切分与版面结构还原。

```python
def translate_document(doc_path: str) -> str:
    # 读取原始文档并执行分块翻译
    with open(doc_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return engine.translate(content)
```

2024 年第四季度测试表明，处理 15,000 字符的长篇技术规范时，系统显存峰值占用稳定在 4.5 GB 以下，翻译成功率达到 100%。详情可参考官方文档 https://example.com/spec 获取更多信息。"""

r2 = translate_sync(server, doc, forced_dir="zh2en")
print("\nTranslated Markdown:")
print(r2["result"])
out = r2["result"]
assert "#" in out, "Markdown heading missing"
assert "https://example.com/spec" in out, "URL missing/corrupted"
assert "def translate_document" in out, "Code missing/corrupted"
assert "2024" in out and "15,000" in out and "4.5" in out and "100%" in out, "Numbers missing/corrupted"
assert "\n\n" in out, "Paragraph structure missing"
print("Test 2 passed successfully!")

server.shutdown()
shutil.rmtree(os.environ["APPDATA"], ignore_errors=True)
print("\nALL REAL MODEL LONG TRANSLATION TESTS PASSED!")
