import os
import sys
from pathlib import Path

APP_NAME = "MaiTranslator"
APP_VERSION = "1.0.0"
MODEL_FILENAME = "HY-MT1.5-7B-Q4_K_M.gguf"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return app_dir()


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def logs_dir() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def vendor_dir() -> Path:
    candidates = [
        app_dir() / "vendor" / "llamacpp",
        app_dir() / "_internal" / "vendor" / "llamacpp",
        resource_dir() / "vendor" / "llamacpp",
    ]
    for c in candidates:
        if (c / "llama-server.exe").exists():
            return c
    return candidates[0]


def model_candidates(model_path: str = "") -> list[Path]:
    result = []
    if model_path:
        p = Path(model_path)
        if not p.is_absolute():
            p = app_dir() / model_path
        result.append(p)
    result.append(data_dir() / "models" / MODEL_FILENAME)
    result.append(app_dir() / "models" / MODEL_FILENAME)
    result.append(app_dir() / "_internal" / "models" / MODEL_FILENAME)
    seen = set()
    unique = []
    for c in result:
        rs = str(c.resolve())
        if rs not in seen:
            seen.add(rs)
            unique.append(c)
    return unique


def find_model(model_path: str = "") -> Path | None:
    for c in model_candidates(model_path):
        if c.is_file() and c.stat().st_size > 1024 * 1024:
            return c
    return None


def server_exe() -> Path | None:
    exe = vendor_dir() / "llama-server.exe"
    return exe if exe.exists() else None
