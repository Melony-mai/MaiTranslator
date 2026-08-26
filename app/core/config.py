import json
import threading
from pathlib import Path

from .paths import data_dir

CONFIG_FILE = None
_lock = threading.RLock()

DEFAULTS = {
    "model_path": "",
    "port": 0,
    "gpu_mode": "auto",
    "ngl": 999,
    "context": 8192,
    "threads": 8,
    "kv_cache": "q8_0",
    "flash_attn": True,
    "temperature": 0.7,
    "top_k": 20,
    "top_p": 0.6,
    "repeat_penalty": 1.05,
    "max_tokens": 4096,
    "auto_copy": True,
    "hotkey_enabled": True,
    "autostart": False,
    "theme": "system",
    "protect_numbers": True,
    "force_replace_glossary": False,
    "floating_at_cursor": True,
    "capture_delay_ms": 260,
    "vram_auto_release_minutes": 5,
}

_cache: dict | None = None


def _file() -> Path:
    global CONFIG_FILE
    if CONFIG_FILE is None:
        CONFIG_FILE = data_dir() / "config.json"
    return Path(CONFIG_FILE)


def load() -> dict:
    global _cache
    with _lock:
        if _cache is not None:
            return _cache
        cfg = dict(DEFAULTS)
        try:
            raw = json.loads(_file().read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if k in DEFAULTS:
                        cfg[k] = v
        except FileNotFoundError:
            pass
        except Exception:
            pass
        _cache = cfg
        return cfg


def get(key: str, default=None):
    cfg = load()
    return cfg.get(key, DEFAULTS.get(key, default))


def set_key(key: str, value) -> None:
    with _lock:
        cfg = load()
        cfg[key] = value
        save()


def save() -> None:
    with _lock:
        cfg = load()
        tmp = _file().with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(_file())


def reset_cache_for_tests() -> None:
    global _cache
    with _lock:
        _cache = None
