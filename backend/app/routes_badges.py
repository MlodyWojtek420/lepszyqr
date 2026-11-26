import asyncio
import base64
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from jinja2 import Environment, FileSystemLoader
from PIL import Image, ImageOps
from playwright.async_api import Browser, async_playwright
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from . import config
from .auth import require_admin
from .db import SessionLocal
from .files import photo_path
from .models import Volunteer
from .qr import qr_svg_data_uri
from .urls import slugify

router = APIRouter(prefix="/api", dependencies=[Depends(require_admin)])

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True)

HEX = r"^#[0-9a-fA-F]{6}$"


class TemplateConfig(BaseModel):
    org_name: str = Field("Nazwa organizacji", max_length=80)
    role_label: str = Field("WOLONTARIUSZ", max_length=40)
    footer_text: str = Field("Zeskanuj kod QR, aby zweryfikować", max_length=120)
    primary_color: str = Field("#1f4e79", pattern=HEX)
    background_color: str = Field("#ffffff", pattern=HEX)
    text_color: str = Field("#1a1a1a", pattern=HEX)
    card_width_mm: float = Field(54, ge=40, le=120)
    card_height_mm: float = Field(86, ge=50, le=200)
    layout: Literal["a4", "card"] = "a4"
    sheet_margin_mm: float = Field(8, ge=0, le=30)
    crop_lines: bool = True


def load_config() -> TemplateConfig:
    try:
        return TemplateConfig(**json.loads(config.TEMPLATE_FILE.read_text(encoding="utf-8")))
    except Exception:
        return TemplateConfig()


# ---------- przeglądarka (Playwright) ----------

_pw = None
_browser: Browser | None = None
_sem = asyncio.Semaphore(2)


async def start_browser() -> None:
    global _pw, _browser
    _pw = await async_playwright().start()
    _browser = await _launch()


async def _launch() -> Browser:
    return await _pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])


async def stop_browser() -> None:
    if _browser:
        await _browser.close()
    if _pw:
        await _pw.stop()


async def render_pdf(html: str) -> bytes:
    global _browser
    async with _sem:
        if _browser is None or not _browser.is_connected():
            _browser = await _launch()
        page = await _browser.new_page()
        try:
            await page.set_content(html, wait_until="load", timeout=180_000)
            return await page.pdf(prefer_css_page_size=True, print_background=True)
        finally:
            await page.close()


# ---------- budowanie HTML ----------

def _jpeg_uri(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.convert("RGB").save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _photo_uri(vid: int | None) -> str:
    try:
        im = Image.open(photo_path(vid))
        im.thumbnail((420, 560))
        return _jpeg_uri(im)
    except Exception:
        return _jpeg_uri(Image.new("RGB", (420, 560), (200, 205, 210)))


def _person(first: str, last: str, url: str, photo: str) -> dict:
    longest = max(len(first), len(last))
    return {
        "first_name": first, "last_name": last, "photo": photo,
        "qr": qr_svg_data_uri(url),
        "name_class": "xsmall" if longest > 22 else "small" if longest > 15 else "",
    }


def load_people(ids: list[int]) -> list[dict]:
    with SessionLocal() as db:
        vols = db.scalars(
            select(Volunteer).where(Volunteer.id.in_(ids))
            .order_by(func.lower(Volunteer.last_name), func.lower(Volunteer.first_name), Volunteer.id)
        ).all()
        return [_person(v.first_name, v.last_name, v.url, _photo_uri(v.id)) for v in vols]


def build_html(cards: list[dict], cfg: TemplateConfig) -> str:
    w, h = cfg.card_width_mm, cfg.card_height_mm
    cols, pages = 1, []
    if cfg.layout == "a4":
        m = cfg.sheet_margin_mm
        cols = max(1, int((210 - 2 * m) // w))
        rows = max(1, int((297 - 2 * m) // h))
        per = cols * rows
        pages = [cards[i:i + per] for i in range(0, len(cards), per)]
        page_size, card_h = "A4", h
    else:
        page_size, card_h = f"{w}mm {h}mm", h - 0.3
    logo = None
    if config.LOGO_FILE.exists():
        logo = "data:image/png;base64," + base64.b64encode(config.LOGO_FILE.read_bytes()).decode()
    return _env.get_template("badge.html.j2").render(
        c=cfg, cards=cards, pages=pages, cols=cols, page_size=page_size, card_h=card_h, logo=logo,
    )


async def make_pdf(cards: list[dict]) -> bytes:
    cfg = load_config()
    html = await run_in_threadpool(build_html, cards, cfg)
    return await render_pdf(html)


# ---------- trasy: szablon ----------

@router.get("/template")
def get_template():
    d = load_config().model_dump()
    d["has_logo"] = config.LOGO_FILE.exists()
    return d


@router.put("/template")
def put_template(body: TemplateConfig):
    config.TEMPLATE_FILE.write_text(body.model_dump_json(indent=2), encoding="utf-8")
    return body


@router.post("/template/logo")
def upload_logo(logo: UploadFile = File(...)):
    data = logo.file.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Logo jest za duże (max 5 MB)")
    try:
        im = Image.open(io.BytesIO(data))
        if im.format not in ("PNG", "JPEG", "WEBP"):
            raise ValueError
        im = ImageOps.exif_transpose(im).convert("RGBA")
        im.thumbnail((600, 600))
        im.save(config.LOGO_FILE, format="PNG")
    except Exception:
        raise HTTPException(400, "Logo musi być plikiem PNG, JPG lub WEBP")
    return {"ok": True}


@router.delete("/template/logo")
def delete_logo():
    config.LOGO_FILE.unlink(missing_ok=True)
    return {"ok": True}


@router.get("/template/logo")
def get_logo():
    if not config.LOGO_FILE.exists():
        raise HTTPException(404)
    return FileResponse(config.LOGO_FILE, media_type="image/png", headers={"Cache-Control": "no-cache"})


@router.get("/template/preview.pdf")
async def preview_pdf():
    person = _person("Jan", "Kowalski", "https://organizacja.pl/wolontariusze/jan-kowalski", _photo_uri(None))
    pdf = await make_pdf([person])
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="podglad.pdf"'})


# ---------- trasy: PDF identyfikatorów ----------

class BadgesIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=5000)


@router.post("/badges/pdf")
async def badges_pdf(body: BadgesIn):
    people = await run_in_threadpool(load_people, body.ids)
    if not people:
        raise HTTPException(404, "Nie znaleziono wolontariuszy")
    pdf = await make_pdf(people)
    name = f"identyfikatory_{datetime.now():%Y%m%d_%H%M}.pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/volunteers/{vid}/badge.pdf")
async def single_badge(vid: int):
    people = await run_in_threadpool(load_people, [vid])
    if not people:
        raise HTTPException(404, "Nie znaleziono wolontariusza")
    p = people[0]
    name = f"identyfikator_{slugify(p['last_name'])}_{slugify(p['first_name'])}.pdf"
    pdf = await make_pdf(people)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})
