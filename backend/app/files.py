import os
from pathlib import Path

from . import config
from .qr import qr_png_bytes


def photo_path(vid: int) -> Path:
    return config.PHOTOS_DIR / f"{vid}.jpg"


def qr_path(vid: int) -> Path:
    return config.QR_DIR / f"{vid}.png"


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def save_photo(vid: int, jpeg: bytes) -> None:
    _atomic_write(photo_path(vid), jpeg)


def write_qr(vid: int, url: str) -> None:
    _atomic_write(qr_path(vid), qr_png_bytes(url))


def delete_files(vid: int) -> None:
    photo_path(vid).unlink(missing_ok=True)
    qr_path(vid).unlink(missing_ok=True)
