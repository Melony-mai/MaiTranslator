from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QPen,
)

from app.core.paths import app_dir, resource_dir

ICON_CANDIDATE_NAMES = ("icon.ico", "icon.png", "app.ico", "app_icon.png")


def bundled_icon_file():
    seen = set()
    base_dirs = [
        resource_dir() / "assets",
        app_dir(),
        app_dir() / "_internal" / "assets",
        app_dir().parents[0],
        Path(__file__).resolve().parents[2],
    ]
    for base in base_dirs:
        for name in ICON_CANDIDATE_NAMES:
            c = base / name
            rs = str(c)
            if rs in seen:
                continue
            seen.add(rs)
            if c.is_file() and c.stat().st_size > 1024:
                return c
    return None


def make_logo_pixmap(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#4f8cff"))
    grad.setColorAt(1.0, QColor("#7a5cff"))
    radius = int(size * 0.22)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.fillPath(path, QBrush(grad))
    f = QFont("Microsoft YaHei", int(size * 0.52))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QPen(QColor("#ffffff")))
    p.drawText(pm.rect(), Qt.AlignCenter, "译")
    p.end()
    return pm


def app_icon() -> QIcon:
    ico = bundled_icon_file()
    if ico is not None:
        icon = QIcon(str(ico))
        if not icon.isNull() and icon.availableSizes():
            return icon
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(make_logo_pixmap(s))
    return icon


def ensure_icon_files() -> tuple[str, str]:
    d = data_dir() / "icons"
    d.mkdir(parents=True, exist_ok=True)
    png_path = d / "app.png"
    if not png_path.exists():
        make_logo_pixmap(256).save(str(png_path), "PNG")
    ico_path = d / "app.ico"
    if not ico_path.exists():
        _write_ico(str(ico_path), [make_logo_pixmap(s) for s in (16, 32, 48, 64, 128, 256)])
    return str(png_path), str(ico_path)


def _png_bytes(pm: QPixmap) -> bytes:
    ba = bytes()
    from PySide6.QtCore import QBuffer, QByteArray

    buf = QBuffer()
    ba_arr = QByteArray()
    buf.setBuffer(ba_arr)
    buf.open(QBuffer.WriteOnly)
    pm.save(buf, "PNG")
    buf.close()
    return bytes(ba_arr)


def _write_ico(path: str, pixmaps: list[QPixmap]) -> None:
    import struct

    images = [(pm.width(), _png_bytes(pm)) for pm in pixmaps]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    body = b""
    for w, data in images:
        b_or_zero = 0 if w >= 256 else w
        entries += struct.pack(
            "<BBBBHHII", b_or_zero, b_or_zero, 0, 0, 1, 32, len(data), offset
        )
        body += data
        offset += len(data)
    with open(path, "wb") as f:
        f.write(header + entries + body)
