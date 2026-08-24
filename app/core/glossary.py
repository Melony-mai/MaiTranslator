import json
import logging
import threading
from pathlib import Path

from .paths import data_dir

log = logging.getLogger(__name__)


class Glossary:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.pairs: list[dict[str, str]] = []
        self.path = data_dir() / "glossary.json"
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                items = raw.get("terms", []) if isinstance(raw, dict) else raw
                self.pairs = []
                for it in items or []:
                    if isinstance(it, dict):
                        src = str(it.get("term", "")).strip()
                        dst = str(it.get("translation", "")).strip()
                        if src and dst:
                            self.pairs.append({"term": src, "translation": dst})
            except FileNotFoundError:
                self.pairs = []
            except Exception as e:
                log.error("词表加载失败: %s", e)
                self.pairs = []

    def save(self) -> None:
        with self._lock:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"terms": self.pairs}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self.path)

    def all_pairs(self) -> list[dict[str, str]]:
        with self._lock:
            return list(self.pairs)

    def matching_pairs(self, text: str, limit: int = 24) -> list[dict[str, str]]:
        lowered = text.lower()
        result = []
        with self._lock:
            for p in self.pairs:
                if p["term"].lower() in lowered:
                    result.append(dict(p))
                    if len(result) >= limit:
                        break
        return result

    def add(self, term: str, translation: str) -> None:
        term = term.strip()
        translation = translation.strip()
        if not term or not translation:
            return
        with self._lock:
            for p in self.pairs:
                if p["term"] == term:
                    p["translation"] = translation
                    self.save()
                    return
            self.pairs.append({"term": term, "translation": translation})
            self.save()

    def remove_at(self, row: int) -> None:
        with self._lock:
            if 0 <= row < len(self.pairs):
                del self.pairs[row]
                self.save()

    def update_at(self, row: int, term: str, translation: str) -> None:
        with self._lock:
            if 0 <= row < len(self.pairs):
                if term.strip() and translation.strip():
                    self.pairs[row] = {"term": term.strip(), "translation": translation.strip()}
                else:
                    del self.pairs[row]
                self.save()

    def import_json(self, path: Path) -> int:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        items = raw.get("terms", []) if isinstance(raw, dict) else raw
        count = 0
        with self._lock:
            for it in items or []:
                if isinstance(it, dict):
                    src = str(it.get("term", "")).strip()
                    dst = str(it.get("translation", "")).strip()
                    if src and dst:
                        self.add(src, dst)
                        count += 1
        return count

    def export_json(self, path: Path) -> None:
        with self._lock:
            Path(path).write_text(
                json.dumps({"terms": self.pairs}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
