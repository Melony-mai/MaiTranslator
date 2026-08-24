import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

OPEN = "\u27E6"
CLOSE = "\u27E7"

FENCED_CODE_RE = re.compile(r"```.*?(?:```|\Z)", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
MD_IMAGE_RE = re.compile(r"!\[[^\]\n]*\]\([^)\n]*\)")
MD_LINK_RE = re.compile(r"\[[^\]\n]+\]\([^)\n]*\)")
URL_STOP = "\uff0c\u3002\uff01\uff1f\uff1b\uff1a\uff09\u3011\u300d\u300f\u201d"
URL_RE = re.compile(
    r"\b(?:https?|ftp)://[^\s<>\"'" + URL_STOP + r"]+|www\.[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+[^\s\uFF0C\u3002\uFF09\u3011\u300D\u300F]*",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
WIN_PATH_RE = re.compile(r"[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n ]+\\)*[^\\/:*?\"<>|\r\n ]*")
UNIX_PATH_RE = re.compile(
    r"(?<![\w~])/(?:usr|home|etc|var|opt|tmp|root|mnt|srv|data)(?:/[\w.-]+)+/?"
)
TAG_RE = re.compile(r"</?[A-Za-z][^<>\n]{0,300}>")
HEX_COLOR_RE = re.compile(r"#[A-Fa-f0-9]{3,8}\b")
MENTION_RE = re.compile(r"@[\w][\w.-]*")
NUM_UNIT_RE = re.compile(
    r"\d+(?:[.,:\-/]\d+)*(?:\s?(?:%|\u00B0C|\u00B0F|px|pt|km|kg|ms|kW|GB|MB|KB|TB))?"
)

BRACKET_PAIRS = [
    (OPEN, CLOSE),
    ("[", "]"),
    ("(", ")"),
    ("{", "}"),
    ("<", ">"),
    ("\u3010", "\u3011"),
    ("\uFF08", "\uFF09"),
    ("\u300A", "\u300B"),
    ("\u3014", "\u3015"),
    ("\u300C", "\u300D"),
    ("\u300E", "\u300F"),
]

_ALT_OPEN = "|".join(re.escape(op) for op, _ in BRACKET_PAIRS)
_ALT_CLOSE = "|".join(re.escape(cl) for _, cl in BRACKET_PAIRS)
PLACEHOLDER_RX = re.compile(rf"(?:{_ALT_OPEN})\s*(\d{{1,5}})\s*(?:{_ALT_CLOSE})")


@dataclass
class ProtectedText:
    source_text: str
    protected_text: str = ""
    segments: list[str] = field(default_factory=list)


_PLACEHOLDER_TOKEN_RX = re.compile(
    "(" + re.escape(OPEN) + r"\d{1,5}" + re.escape(CLOSE) + ")"
)


def _sub_outside_placeholders(pattern: re.Pattern, repl, text: str) -> str:
    tokens = _PLACEHOLDER_TOKEN_RX.split(text)
    for i in range(0, len(tokens), 2):
        if tokens[i]:
            tokens[i] = pattern.sub(repl, tokens[i])
    return "".join(tokens)


def protect(text: str, protect_numbers: bool = True) -> ProtectedText:
    pt = ProtectedText(source_text=text)

    def _repl(m: re.Match) -> str:
        pt.segments.append(m.group(0))
        return f"{OPEN}{len(pt.segments)}{CLOSE}"

    patterns = [
        FENCED_CODE_RE,
        INLINE_CODE_RE,
        MD_IMAGE_RE,
        MD_LINK_RE,
        URL_RE,
        EMAIL_RE,
        WIN_PATH_RE,
        UNIX_PATH_RE,
        TAG_RE,
        HEX_COLOR_RE,
        MENTION_RE,
    ]
    if protect_numbers:
        patterns.append(NUM_UNIT_RE)

    current = text
    for pat in patterns:
        current = _sub_outside_placeholders(pat, _repl, current)
    pt.protected_text = current
    return pt


def restore(translated: str, pt: ProtectedText) -> str:
    if not pt.segments:
        return translated
    out = translated
    search_from = 0
    missing = []
    for idx, original in enumerate(pt.segments, start=1):
        found = None
        for m in PLACEHOLDER_RX.finditer(out, search_from):
            if int(m.group(1)) == idx:
                found = m
                break
        if found is None:
            for m in PLACEHOLDER_RX.finditer(out):
                if int(m.group(1)) == idx:
                    found = m
                    break
        if found is None:
            missing.append(idx)
            continue
        out = out[: found.start()] + original + out[found.end() :]
        search_from = found.start() + len(original)
    for idx in missing:
        log.warning("占位符 %s 未能在译文中恢复", idx)
        out = PLACEHOLDER_RX.sub(lambda m, i=idx: "" if int(m.group(1)) == i else m.group(0), out)
    return out


def postprocess(result: str, source: str) -> str:
    out = result.strip()
    quote_pairs = [('"', '"'), ("\u201c", "\u201d"), ("'", "'"), ("\u2018", "\u2019")]
    changed = True
    while changed and len(out) >= 2:
        changed = False
        for op, cl in quote_pairs:
            if (
                out.startswith(op)
                and out.endswith(cl)
                and len(out) > 2
                and not source.strip().startswith(op)
            ):
                out = out[1:-1].strip()
                changed = True
                break
    out = re.sub(r"^(译文|翻译结果|翻译)[:：]\s*", "", out)
    return out.strip()
