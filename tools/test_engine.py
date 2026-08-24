import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="maitranslator_test_")
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

state_log = []
server.stateChanged.connect(lambda s, m: (state_log.append((s, m)), print(f"[engine] {s} {m}")))

results = {}
quit_timer = QTimer()


def wait_ready(timeout_s=300.0):
    server.start()
    elapsed = 0.0
    while server.state != LlamaServer.STATE_READY and elapsed < timeout_s:
        app.processEvents()
        QTimer.singleShot(50, lambda: None)
        import time

        time.sleep(0.05)
        app.processEvents()
        elapsed += 0.1
        if server.state == LlamaServer.STATE_ERROR:
            raise RuntimeError(f"engine error: {server._error_msg}")
    if server.state != LlamaServer.STATE_READY:
        raise RuntimeError("timeout waiting for engine")
    print("ENGINE READY, gpu_active =", server.gpu_active)


def t(text, forced=None, pairs_glossary=False):
    g = glossary if pairs_glossary else None
    r = translate_sync(server, text, forced_dir=forced, glossary=g)
    results[text[:20]] = r
    return r


wait_ready()

print("\n===== TEST 1: zh -> en =====")
r = t("今天天气真好，我们一起去公园散步吧。")
print("SRC:", r["source"])
print("DST:", r["result"])
assert r["src_lang"] == "zh" and r["tgt_lang"] == "en"
assert len(r["result"]) > 5

print("\n===== TEST 2: en -> zh =====")
r = t("The quick brown fox jumps over the lazy dog.")
print("SRC:", r["source"])
print("DST:", r["result"])
assert r["src_lang"] == "en" and r["tgt_lang"] == "zh"
assert len(r["result"]) > 3

print("\n===== TEST 3: markdown / code / URL / number preservation =====")
md = """# 发布说明 v2.1

请查看 https://github.com/example/repo 获取详情，或发邮件到 support@example.com。

安装命令：
```bash
pip install mai-translator==2.1.0
```

2024 年销量增长 35%，达到 1,250 万元。"""

r = t(md)
out = r["result"]
print(out)
assert "https://github.com/example/repo" in out, "URL broken"
assert "support@example.com" in out, "email broken"
assert "pip install mai-translator==2.1.0" in out, "code broken"
assert "2024" in out and "35%" in out and "1,250" in out, "numbers broken"

print("\n===== TEST 4: glossary priority =====")
glossary.add("大模型", "LLM")
glossary.add("混元", "Hunyuan")
r = t("我们的大模型产品混元已经上线了。", pairs_glossary=True)
print(r["result"])
assert "LLM" in r["result"], "glossary term LLM not used"
assert "Hunyuan" in r["result"], "glossary term Hunyuan not used"

print("\n===== TEST 5: mixed text direction =====")
r = t("这个 API 的响应速度是 120ms 左右")
print(r["result"])
assert r["src_lang"] == "zh"

print("\nALL ENGINE TESTS PASSED")
server.shutdown()
shutil.rmtree(os.environ["APPDATA"], ignore_errors=True)
