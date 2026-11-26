import io
import zipfile
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import config
from .auth import require_admin
from .db import get_db
from .files import delete_files, photo_path, qr_path, save_photo, write_qr
from .images import ImageError, process_photo
from .models import Volunteer, now
from .qr import qr_png_bytes
from .urls import clean_name, name_key, slugify, validate_url

router = APIRouter(prefix="/api/volunteers", dependencies=[Depends(require_admin)])


def vdict(v: Volunteer) -> dict:
    ts = int(v.updated_at.timestamp())
    return {
        "id": v.id,
        "first_name": v.first_name,
        "last_name": v.last_name,
        "url": v.url,
        "status": v.status,
        "photo_url": f"/api/volunteers/{v.id}/photo?v={ts}",
        "qr_url": f"/api/volunteers/{v.id}/qr.png?v={ts}",
        "created_at": v.created_at.isoformat(),
    }


def existing_name_map(db: Session) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for vid, first, last in db.execute(select(Volunteer.id, Volunteer.first_name, Volunteer.last_name)):
        out.setdefault(name_key(first, last), []).append(vid)
    return out


def get_or_404(db: Session, vid: int) -> Volunteer:
    v = db.get(Volunteer, vid)
    if not v:
        raise HTTPException(404, "Nie znaleziono wolontariusza")
    return v


def bad_request(e: Exception):
    raise HTTPException(400, str(e))


# ---------- lista ----------

@router.get("")
def list_volunteers(q: str = "", status: str = "", db: Session = Depends(get_db)):
    stmt = select(Volunteer)
    if status in config.STATUSES:
        stmt = stmt.where(Volunteer.status == status)
    for term in q.split():
        esc = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{esc}%"
        stmt = stmt.where(or_(
            Volunteer.first_name.ilike(like, escape="\\"),
            Volunteer.last_name.ilike(like, escape="\\"),
            Volunteer.url.ilike(like, escape="\\"),
        ))
    stmt = stmt.order_by(func.lower(Volunteer.last_name), func.lower(Volunteer.first_name), Volunteer.id)
    return [vdict(v) for v in db.scalars(stmt)]


# ---------- operacje zbiorcze (przed trasami /{vid}) ----------

class IdsIn(BaseModel):
    ids: list[int] = Field(max_length=10000)


class BulkStatusIn(IdsIn):
    status: Literal["active", "inactive"]


class RegenIn(BaseModel):
    ids: list[int] | None = None  # None = wszyscy


class TransformIn(IdsIn):
    mode: Literal["replace", "pattern"]
    find: str = ""
    replace: str = ""
    pattern: str = ""
    apply: bool = False


@router.post("/bulk-status")
def bulk_status(body: BulkStatusIn, db: Session = Depends(get_db)):
    vols = db.scalars(select(Volunteer).where(Volunteer.id.in_(body.ids))).all()
    for v in vols:
        v.status = body.status
    db.commit()
    return {"count": len(vols)}


@router.post("/bulk-delete")
def bulk_delete(body: IdsIn, db: Session = Depends(get_db)):
    vols = db.scalars(select(Volunteer).where(Volunteer.id.in_(body.ids))).all()
    ids = [v.id for v in vols]
    for v in vols:
        db.delete(v)
    db.commit()
    for vid in ids:
        delete_files(vid)
    return {"count": len(ids)}


@router.post("/regenerate-qr")
def regenerate_qr(body: RegenIn, db: Session = Depends(get_db)):
    stmt = select(Volunteer)
    if body.ids is not None:
        stmt = stmt.where(Volunteer.id.in_(body.ids))
    vols = db.scalars(stmt).all()
    for v in vols:
        write_qr(v.id, v.url)
        v.qr_generated_at = now()
    db.commit()
    return {"count": len(vols)}


@router.post("/qr-zip")
def qr_zip(body: IdsIn, db: Session = Depends(get_db)):
    vols = db.scalars(
        select(Volunteer).where(Volunteer.id.in_(body.ids))
        .order_by(func.lower(Volunteer.last_name), func.lower(Volunteer.first_name))
    ).all()
    if not vols:
        raise HTTPException(404, "Nie wybrano wolontariuszy")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for v in vols:
            p = qr_path(v.id)
            data = p.read_bytes() if p.exists() else qr_png_bytes(v.url)
            zf.writestr(f"{slugify(v.last_name)}_{slugify(v.first_name)}_{v.id}.png", data)
    return Response(
        buf.getvalue(), media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="kody-qr.zip"'},
    )


@router.post("/bulk-urls/transform")
def transform_urls(body: TransformIn, db: Session = Depends(get_db)):
    if body.mode == "replace" and not body.find:
        raise HTTPException(400, "Podaj fragment adresu do zamiany")
    if body.mode == "pattern" and not body.pattern.strip():
        raise HTTPException(400, "Podaj wzorzec adresu")
    vols = db.scalars(select(Volunteer).where(Volunteer.id.in_(body.ids))).all()
    vols.sort(key=lambda v: (v.last_name.lower(), v.first_name.lower()))

    rows = []
    for v in vols:
        if body.mode == "replace":
            new = v.url.replace(body.find, body.replace)
        else:
            f, l = slugify(v.first_name), slugify(v.last_name)
            new = (body.pattern.strip()
                   .replace("{slug}", "-".join(x for x in (f, l) if x))
                   .replace("{first_name}", f).replace("{last_name}", l)
                   .replace("{id}", str(v.id)))
        row = {"id": v.id, "name": f"{v.last_name} {v.first_name}", "old_url": v.url, "new_url": new}
        try:
            row["new_url"] = new = validate_url(new)
        except ValueError as e:
            row["error"] = str(e)
        rows.append(row)

    counts: dict[str, int] = {}
    for r in rows:
        if "error" not in r:
            counts[r["new_url"]] = counts.get(r["new_url"], 0) + 1
    for r in rows:
        r["changed"] = "error" not in r and r["new_url"] != r["old_url"]
        if "error" not in r and counts[r["new_url"]] > 1:
            r["warning"] = "Ten sam adres otrzyma więcej niż jedna osoba"

    changed = [r for r in rows if r["changed"]]
    if body.apply:
        by_id = {v.id: v for v in vols}
        for r in changed:
            by_id[r["id"]].url = r["new_url"]
        db.commit()
        for r in changed:
            write_qr(r["id"], r["new_url"])
            by_id[r["id"]].qr_generated_at = now()
        db.commit()
    return {"rows": rows, "changed": len(changed), "applied": body.apply}


# ---------- pojedynczy wolontariusz ----------

@router.post("", status_code=201)
def create_volunteer(
    first_name: str = Form(...), last_name: str = Form(...), url: str = Form(...),
    status: str = Form("active"), force: bool = Form(False),
    photo: UploadFile = File(...), db: Session = Depends(get_db),
):
    try:
        first = clean_name(first_name, "imię")
        last = clean_name(last_name, "nazwisko")
        url = validate_url(url)
    except ValueError as e:
        bad_request(e)
    if status not in config.STATUSES:
        raise HTTPException(400, "Niepoprawny status")
    try:
        jpeg = process_photo(photo.file.read(config.MAX_PHOTO_BYTES + 1))
    except ImageError as e:
        bad_request(e)
    if not force and name_key(first, last) in existing_name_map(db):
        raise HTTPException(409, detail={
            "code": "duplicate",
            "message": "Wolontariusz o takim imieniu i nazwisku już istnieje.",
        })
    v = Volunteer(first_name=first, last_name=last, url=url, status=status)
    db.add(v)
    db.flush()
    vid = v.id
    try:
        save_photo(vid, jpeg)
        write_qr(vid, url)
        v.qr_generated_at = now()
        db.commit()
    except Exception:
        db.rollback()
        delete_files(vid)
        raise
    return vdict(v)


@router.put("/{vid}")
def update_volunteer(
    vid: int,
    first_name: str = Form(...), last_name: str = Form(...), url: str = Form(...),
    status: str = Form(None), photo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    v = get_or_404(db, vid)
    try:
        first = clean_name(first_name, "imię")
        last = clean_name(last_name, "nazwisko")
        url = validate_url(url)
    except ValueError as e:
        bad_request(e)
    if status is not None and status not in config.STATUSES:
        raise HTTPException(400, "Niepoprawny status")
    jpeg = None
    if photo is not None and photo.filename:
        try:
            jpeg = process_photo(photo.file.read(config.MAX_PHOTO_BYTES + 1))
        except ImageError as e:
            bad_request(e)
    url_changed = url != v.url
    v.first_name, v.last_name, v.url = first, last, url
    if status:
        v.status = status
    v.updated_at = now()
    db.commit()
    if jpeg:
        save_photo(v.id, jpeg)
    if url_changed or not qr_path(v.id).exists():
        write_qr(v.id, url)
        v.qr_generated_at = now()
        db.commit()
    return vdict(v)


class StatusIn(BaseModel):
    status: Literal["active", "inactive"]


class UrlIn(BaseModel):
    url: str


@router.patch("/{vid}/status")
def set_status(vid: int, body: StatusIn, db: Session = Depends(get_db)):
    v = get_or_404(db, vid)
    v.status = body.status
    db.commit()
    return vdict(v)


@router.patch("/{vid}/url")
def set_url(vid: int, body: UrlIn, db: Session = Depends(get_db)):
    v = get_or_404(db, vid)
    try:
        url = validate_url(body.url)
    except ValueError as e:
        bad_request(e)
    v.url = url
    db.commit()
    write_qr(v.id, url)
    v.qr_generated_at = now()
    db.commit()
    return vdict(v)


@router.delete("/{vid}")
def delete_volunteer(vid: int, db: Session = Depends(get_db)):
    v = get_or_404(db, vid)
    db.delete(v)
    db.commit()
    delete_files(vid)
    return {"ok": True}


@router.get("/{vid}/photo")
def get_photo(vid: int):
    p = photo_path(vid)
    if not p.exists():
        raise HTTPException(404, "Brak zdjęcia")
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{vid}/qr.png")
def get_qr(vid: int, db: Session = Depends(get_db)):
    v = get_or_404(db, vid)
    p = qr_path(vid)
    if not p.exists():
        write_qr(vid, v.url)
    return FileResponse(p, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
