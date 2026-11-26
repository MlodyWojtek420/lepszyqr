import base64
import io

import qrcode
from PIL import Image, ImageDraw
from qrcode.constants import ERROR_CORRECT_M


def _matrix(url: str) -> list[list[bool]]:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=1, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.get_matrix()  # zawiera margines (quiet zone)


def qr_png_bytes(url: str, scale: int = 12) -> bytes:
    m = _matrix(url)
    n = len(m)
    im = Image.new("L", (n * scale, n * scale), 255)
    d = ImageDraw.Draw(im)
    for y, row in enumerate(m):
        for x, on in enumerate(row):
            if on:
                d.rectangle([x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1], fill=0)
    out = io.BytesIO()
    im.save(out, format="PNG", optimize=True)
    return out.getvalue()


def qr_svg(url: str) -> str:
    m = _matrix(url)
    n = len(m)
    parts = []
    for y, row in enumerate(m):
        x = 0
        while x < n:
            if row[x]:
                s = x
                while x < n and row[x]:
                    x += 1
                parts.append(f"M{s} {y}h{x - s}v1h-{x - s}z")
            else:
                x += 1
    d = "".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" shape-rendering="crispEdges">'
        f'<rect width="{n}" height="{n}" fill="#fff"/><path d="{d}" fill="#000"/></svg>'
    )


def qr_svg_data_uri(url: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(qr_svg(url).encode()).decode()
