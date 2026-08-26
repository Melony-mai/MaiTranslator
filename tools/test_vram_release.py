import io
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="mt_vram_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

qt_app = QApplication(sys.argv[:1])

from app.core.logger import setup_logging

setup_logging()

from app.core import config
from app.core.engine import LlamaServer


def dedicated_mib(pid: int) -> float:
    """Per-process dedicated GPU memory via Windows GPU counters; 0 if none."""
    ps = (
        "$s=(Get-Counter '\\GPU Process Memory(pid_%d*)\\Dedicated Usage' "
        "-ErrorAction SilentlyContinue).CounterSamples;"
        "if($s){($s|Measure-Object -Property CookedValue -Sum).Sum}else{0}" % pid
    )
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True, text=True, timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ).stdout.strip()
    try:
        return float(out) / 1024.0 / 1024.0
    except ValueError:
        return -1.0


def wait_state(server: LlamaServer, want_gpu: bool | None, timeout: float = 300.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qt_app.processEvents()
        if server.state == LlamaServer.STATE_READY:
            if want_gpu is None or server.gpu_active == want_gpu:
                return
        if server.state == LlamaServer.STATE_ERROR:
            raise RuntimeError(f"engine error: {server._error_msg}")
        time.sleep(0.2)
    raise TimeoutError(f"timeout waiting state={server.state} gpu={server.gpu_active}")


config.set_key("gpu_mode", "auto")
config.set_key("context", 2048)

server = LlamaServer()
print("[1] start_standby (RAM-resident)...")
server.start_standby()
wait_state(server, want_gpu=False)
pid = server._proc.pid
time.sleep(3)
vram_standby = dedicated_mib(pid)
print(f"    ready pid={pid}, dedicated VRAM = {vram_standby:.1f} MB")
assert vram_standby < 100, f"standby mode must use ~0 VRAM, got {vram_standby:.1f} MB"

print("[2] ensure_ready_async -> on-demand GPU load...")
status = server.ensure_ready_async()
print(f"    status={status}")
assert status == "started"
wait_state(server, want_gpu=True)
pid2 = server._proc.pid
time.sleep(5)
vram_gpu = dedicated_mib(pid2)
print(f"    ready pid={pid2}, dedicated VRAM = {vram_gpu:.1f} MB")
assert vram_gpu > 500, f"GPU mode should hold model in VRAM, got {vram_gpu:.1f} MB"

print("[3] release_vram -> back to RAM-resident...")
ok = server.release_vram(reason="test")
print(f"    release_vram -> {ok}")
assert ok
wait_state(server, want_gpu=False)
pid3 = server._proc.pid
# give WDDM a moment to reclaim and health to settle
time.sleep(5)
vram_released = dedicated_mib(pid3)
old_left = dedicated_mib(pid2)
print(f"    ready pid={pid3}, dedicated VRAM = {vram_released:.1f} MB (old proc residue {old_left:.1f} MB)")
assert vram_released < 100, f"after release must be ~0 VRAM, got {vram_released:.1f} MB"
assert old_left < 100, f"old GPU process still holds {old_left:.1f} MB"

print("[4] cleanup")
server.stop()
time.sleep(2)
final = max(dedicated_mib(p) for p in (pid, pid2, pid3))
print(f"    residual after stop = {final:.1f} MB")

print("ALL VRAM TESTS PASSED:")
print(f"  standby={vram_standby:.1f}MB gpu={vram_gpu:.1f}MB released={vram_released:.1f}MB stopped={final:.1f}MB")
