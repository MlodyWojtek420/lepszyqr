import io

from PIL import Image, ImageOps

from . import config

Image.MAX_IMAGE_PIXELS = 60_000_000
PHOTO_SIZE = (600, 800)  # proporcje 3:4


class ImageError(ValueError):
    pass


def process_photo(data: bytes) -> bytes:
    """Waliduje zdjęcie i zapisuje je jako JPEG 600x800 (kadr 3:4)."""
    if not data:
        raise ImageError("Pusty plik zdjęcia")
    if len(data) > config.MAX_PHOTO_BYTES:
        raise ImageError("Zdjęcie jest za duże (max 10 MB)")
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()
        im = Image.open(io.BytesIO(data))
        if im.format not in ("JPEG", "PNG", "WEBP"):
            raise ImageError("Dozwolone formaty zdjęć: JPG, PNG, WEBP")
        im = ImageOps.exif_transpose(im).convert("RGBA")
    except ImageError:
        raise
    except Exception:
        raise ImageError("Plik nie jest poprawnym zdjęciem (JPG, PNG lub WEBP)")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    im = ImageOps.fit(bg.convert("RGB"), PHOTO_SIZE, method=Image.LANCZOS, centering=(0.5, 0.35))
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()
