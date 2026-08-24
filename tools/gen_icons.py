import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication

from app.ui.icons import make_logo_pixmap

app = QApplication([])

root = Path(__file__).resolve().parents[1]
build_assets = root / "build" / "assets"
build_assets.mkdir(parents=True, exist_ok=True)

source_ico = root / "icon.ico"
source_png = root / "icon.png"
if source_ico.is_file():
    loaded = QPixmap(str(source_ico))
    assert not loaded.isNull(), "icon.ico is not a valid image"
    base = loaded
    print(f"using custom icon: {source_ico} ({base.width()}x{base.height()})")
elif source_png.is_file():
    base = QPixmap(str(source_png))
    assert not base.isNull(), "icon.png is not a valid image"
    print(f"using custom icon: {source_png} ({base.width()}x{base.height()})")
else:
    print("no custom icon in project root; falling back to generated logo")
    base = make_logo_pixmap(256)


def scaled(size: int) -> QPixmap:
    if base.width() == size:
        return base
    return base.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)


def _png_bytes(pm: QPixmap) -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray

    buf = QBuffer()
    arr = QByteArray()
    buf.setBuffer(arr)
    buf.open(QBuffer.WriteOnly)
    pm.save(buf, "PNG")
    buf.close()
    return bytes(arr)


def write_ico(path: Path, pixmaps: list[QPixmap]) -> None:
    import struct

    images = [(pm.width(), _png_bytes(pm)) for pm in pixmaps]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    body = b""
    for w, data in images:
        b_or_zero = 0 if w >= 256 else w
        entries += struct.pack("<BBBBHHII", b_or_zero, b_or_zero, 0, 0, 1, 32, len(data), offset)
        body += data
        offset += len(data)
    path.write_bytes(header + entries + body)


sizes = [256, 128, 64, 48, 32, 24, 16]
pixmaps = [scaled(s) for s in sizes]
ico_path = build_assets / "app.ico"
write_ico(ico_path, pixmaps)
print("wrote", ico_path)

png_path = build_assets / "app_icon.png"
scaled(256).save(str(png_path), "PNG")
print("wrote", png_path)

check = QIcon(str(ico_path))
print("verify ico loads:", not check.isNull(), "sizes:", [(s.width(), s.height()) for s in check.availableSizes()])
assert not check.isNull()
print("ICON CONVERSION OK")
