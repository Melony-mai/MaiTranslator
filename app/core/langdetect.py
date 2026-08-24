import re
import unicodedata

_CJK_RANGES = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x20000, 0x2A6DF),
)

_CJK_PUNCT = set("，。！？；：、（）【】《》「」『』…—·‘’“”")

_URL_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S+|www\.\S+", re.IGNORECASE)


def _is_cjk_char(ch: str) -> bool:
    cp = ord(ch)
    for lo, hi in _CJK_RANGES:
        if lo <= cp <= hi:
            return True
    return ch in _CJK_PUNCT


def _is_latin_letter(ch: str) -> bool:
    return ch.isascii() and ch.isalpha()


def detect_language(text: str) -> str:
    cjk = 0
    latin = 0
    for ch in text:
        if _is_cjk_char(ch):
            cjk += 1
        elif _is_latin_letter(ch):
            latin += 1
    if cjk == 0 and latin == 0:
        return "zh" if any(unicodedata.name(c, "").startswith("CJK") for c in text) else "en"
    if cjk == 0:
        return "en"
    if latin == 0:
        return "zh"
    return "zh" if cjk / max(1, cjk + latin) >= 0.22 else "en"


def direction(text: str, forced: str | None = None) -> tuple[str, str]:
    if forced == "zh2en":
        return "zh", "en"
    if forced == "en2zh":
        return "en", "zh"
    src = detect_language(text)
    tgt = "en" if src == "zh" else "zh"
    return src, tgt


def strip_url_noise(text: str) -> str:
    return _URL_RE.sub("", text)
