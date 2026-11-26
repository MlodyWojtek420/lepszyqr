import io
import json
import os
import re
import secrets
import shutil
import time
import zipfile
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from openpyxl import Workbook, load_workbook
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import config
from .auth import require_admin
from .db import get_db
from .files import save_photo, write_qr
from .images import ImageError, process_photo
from .models import Volunteer, now
from .routes_volunteers import existing_name_map
from .urls import clean_name, name_key, validate_url

router = APIRouter(prefix="/api/import", dependencies=[Depends(require_admin)])

ALIASES = {
    "first_name": {"first_name", "imie", "imię"},
    "last_name": {"last_name", "nazwisko"},
    "photo": {"photo", "zdjecie", "zdjęcie"},
    "url": {"url", "adres", "adres_url"},
    "id": {"id"},
}
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,40}$")


def _cell(r, i) -> str:
    v = r[i] if i < len(r) else None
    return "" if v is None else str(v).strip()


def read_sheet(data: bytes, required: list[str]) -> tuple[dict, list[dict]]:
    if len(data) > config.MAX_XLSX_BYTES:
        raise HTTPException(400, "Plik Excel jest za duży")
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        raise HTTPException(400, "Nie udało się otworzyć pliku. Wymagany format .xlsx")
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    header = next(it, None)
    if not header:
        raise HTTPException(400, "Plik Excel jest pusty")
    idx: dict[str, int] = {}
    for i, h in enumerate(header):
        key = str(h).strip().lower() if h is not None else ""
        for canon, names in ALIASES.items():
            if key in names and canon not in idx:
                idx[canon] = i
    missing = [c for c in required if c not in idx]
    if missing:
        raise HTTPException(400, f"Brak wymaganych kolumn: {', '.join(missing)}")
    rows = []
    for n, r in enumerate(it, start=2):
        rec = {c: _cell(r, i) for c, i in idx.items()}
        if not any(rec.values()):
            continue
        rec["_row"] = n
        rows.append(rec)
        if len(rows) > config.MAX_IMPORT_ROWS:
            raise HTTPException(400, f"Za dużo wierszy (max {config.MAX_IMPORT_ROWS})")
    wb.close()
    return idx, rows


def _tdir(token: str):
    if not TOKEN_RE.match(token):
        raise HTTPException(400, "Niepoprawny token importu")
    d = config.TMP_DIR / "import" / token
    if not d.is_dir():
        raise HTTPException(404, "Import wygasł – wgraj pliki ponownie")
    return d


def _cleanup_tmp() -> None:
    base = config.TMP_DIR / "import"
    base.mkdir(parents=True, exist_ok=True)
    for d in base.iterdir():
        if d.is_dir() and time.time() - d.stat().st_mtime > 24 * 3600:
            shutil.rmtree(d, ignore_errors=True)


@router.get("/template.xlsx")
def sample_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.title = "wolontariusze"
    ws.append(["first_name", "last_name", "photo", "url"])
    ws.append(["Jan", "Kowalski", "jan.jpg", "https://organizacja.pl/wolontariusze/jan-kowalski"])
    ws.append(["Anna", "Nowak", "anna.jpg", "https://organizacja.pl/wolontariusze/anna-nowak"])
    ws.append(["Piotr", "Wiśniewski", "piotr.jpg", "https://organizacja.pl/wolontariusze/piotr-wisniewski"])
    for col, w in zip("ABCD", (18, 22, 18, 60)):
        ws.column_dimensions[col].width = w
    buf = io.BytesIO()
    wb.save(buf)
    return Response(
        buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="wzor-import.xlsx"'},
    )


# ---------- import wolontariuszy: podgląd ----------

@router.post("/preview")
def preview(xlsx: UploadFile = File(...), photos: UploadFile = File(...), db: Session = Depends(get_db)):
    _, rows = read_sheet(xlsx.file.read(config.MAX_XLSX_BYTES + 1), ["first_name", "last_name", "photo", "url"])
    if not rows:
        raise HTTPException(400, "Plik Excel nie zawiera żadnych wierszy z danymi")
    zdata = photos.file.read(config.MAX_ZIP_BYTES + 1)
    if len(zdata) > config.MAX_ZIP_BYTES:
        raise HTTPException(400, "Archiwum ZIP jest za duże")
    try:
        zf = zipfile.ZipFile(io.BytesIO(zdata))
    except zipfile.BadZipFile:
        raise HTTPException(400, "Plik ze zdjęciami nie jest poprawnym archiwum ZIP")
    infos = [i for i in zf.infolist() if not i.is_dir()]
    if sum(i.file_size for i in infos) > config.MAX_ZIP_UNCOMPRESSED:
        raise HTTPException(400, "Archiwum ZIP jest zbyt duże po rozpakowaniu")

    files: dict[str, zipfile.ZipInfo] = {}
    ambiguous: set[str] = set()
    for i in infos:
        if "__macosx" in i.filename.lower():
            continue
        base = os.path.basename(i.filename.replace("\\", "/")).lower()
        if not base or base.startswith("."):
            continue
        if base in files:
            ambiguous.add(base)
        files[base] = i

    _cleanup_tmp()
    token = secrets.token_urlsafe(16)
    tdir = config.TMP_DIR / "import" / token
    tdir.mkdir(parents=True)
    existing = existing_name_map(db)
    seen: dict[str, int] = {}
    out = []

    for rec in rows:
        n = rec["_row"]
        errors: list[str] = []
        warnings: list[str] = []
        first, last, url = rec["first_name"], rec["last_name"], rec["url"]
        for label, fn in (("imię", "first"), ("nazwisko", "last")):
            try:
                val = clean_name(first if fn == "first" else last, label)
                if fn == "first":
                    first = val
                else:
                    last = val
            except ValueError as e:
                errors.append(str(e))
        try:
            url = validate_url(url)
        except ValueError as e:
            errors.append(str(e))

        photo_file = None
        pname = os.path.basename(rec["photo"].replace("\\", "/")).lower()
        if not pname:
            errors.append("Brak nazwy pliku zdjęcia")
        elif pname in ambiguous:
            errors.append("Nazwa zdjęcia występuje w archiwum więcej niż raz")
        elif pname not in files:
            errors.append(f"Nie znaleziono zdjęcia „{rec['photo']}” w archiwum ZIP")
        else:
            try:
                with zf.open(files[pname]) as fh:
                    jpeg = process_photo(fh.read(config.MAX_PHOTO_BYTES + 1))
                (tdir / f"{n}.jpg").write_bytes(jpeg)
                photo_file = f"{n}.jpg"
            except ImageError as e:
                errors.append(str(e))

        status = "ok"
        existing_id = None
        if not errors:
            key = name_key(first, last)
            if key in seen:
                errors.append(f"Duplikat w pliku (taka osoba jest już w wierszu {seen[key]})")
            else:
                seen[key] = n
                ids = existing.get(key)
                if ids and len(ids) > 1:
                    errors.append("W bazie jest kilku wolontariuszy o tym imieniu i nazwisku – zaktualizuj ręcznie")
                elif ids:
                    status, existing_id = "duplicate", ids[0]
                    warnings.append("Wolontariusz już istnieje w bazie")
        if errors:
            status = "error"
        out.append({
            "row": n, "first_name": first, "last_name": last, "url": url,
            "photo_file": photo_file, "status": status, "existing_id": existing_id,
            "messages": errors + warnings,
        })

    (tdir / "rows.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    summary = {s: sum(1 for r in out if r["status"] == s) for s in ("ok", "duplicate", "error")}
    summary["total"] = len(out)
    return {"token": token, "summary": summary, "rows": out}


@router.get("/{token}/photo/{row}")
def preview_photo(token: str, row: int):
    p = _tdir(token) / f"{int(row)}.jpg"
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


class CommitIn(BaseModel):
    token: str
    on_duplicate: Literal["skip", "update"] = "skip"


@router.post("/commit")
def commit(body: CommitIn, db: Session = Depends(get_db)):
    tdir = _tdir(body.token)
    rows = json.loads((tdir / "rows.json").read_text(encoding="utf-8"))
    existing = existing_name_map(db)
    created = updated = skipped = 0
    pending: list[tuple[int, bytes, str]] = []
    try:
        for r in rows:
            if r["status"] == "error" or not r["photo_file"]:
                skipped += 1
                continue
            jpeg = (tdir / r["photo_file"]).read_bytes()
            key = name_key(r["first_name"], r["last_name"])
            ids = existing.get(key)
            if ids:
                if body.on_duplicate == "update" and len(ids) == 1:
                    v = db.get(Volunteer, ids[0])
                    v.url = r["url"]
                    v.updated_at = now()
                    pending.append((v.id, jpeg, r["url"]))
                    updated += 1
                else:
                    skipped += 1
                continue
            v = Volunteer(first_name=r["first_name"], last_name=r["last_name"], url=r["url"], status="active")
            db.add(v)
            db.flush()
            existing[key] = [v.id]
            pending.append((v.id, jpeg, r["url"]))
            created += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    for vid, jpeg, url in pending:
        save_photo(vid, jpeg)
        write_qr(vid, url)
        v = db.get(Volunteer, vid)
        v.qr_generated_at = now()
    db.commit()
    shutil.rmtree(tdir, ignore_errors=True)
    return {"created": created, "updated": updated, "skipped": skipped}


# ---------- masowy import adresów URL ----------

@router.post("/urls")
def import_urls(xlsx: UploadFile = File(...), apply: bool = False, db: Session = Depends(get_db)):
    idx, rows = read_sheet(xlsx.file.read(config.MAX_XLSX_BYTES + 1), ["url"])
    if "id" not in idx and not ("first_name" in idx and "last_name" in idx):
        raise HTTPException(400, "Plik musi zawierać kolumnę id albo kolumny first_name i last_name")
    existing = existing_name_map(db)
    out = []
    to_apply: list[tuple[Volunteer, str]] = []
    for rec in rows:
        row = {"row": rec["_row"], "name": "", "old_url": "", "new_url": rec.get("url", ""), "status": "error", "message": ""}
        v = None
        if rec.get("id"):
            try:
                v = db.get(Volunteer, int(float(rec["id"])))
            except ValueError:
                v = None
            if not v:
                row["message"] = "Nie ma wolontariusza o takim ID"
        elif rec.get("first_name") and rec.get("last_name"):
            ids = existing.get(name_key(rec["first_name"], rec["last_name"]), [])
            if not ids:
                row["message"] = "Nie znaleziono wolontariusza o takim imieniu i nazwisku"
            elif len(ids) > 1:
                row["message"] = "Kilku wolontariuszy o tym samym imieniu i nazwisku – użyj kolumny id"
            else:
                v = db.get(Volunteer, ids[0])
        else:
            row["message"] = "Brak ID lub imienia i nazwiska"
        if v:
            row["name"] = f"{v.last_name} {v.first_name}"
            row["old_url"] = v.url
            try:
                new = validate_url(rec.get("url", ""))
                row["new_url"] = new
                if new == v.url:
                    row["status"], row["message"] = "same", "Bez zmian"
                else:
                    row["status"] = "change"
                    to_apply.append((v, new))
            except ValueError as e:
                row["message"] = str(e)
        out.append(row)
    if apply:
        for v, new in to_apply:
            v.url = new
        db.commit()
        for v, new in to_apply:
            write_qr(v.id, new)
            v.qr_generated_at = now()
        db.commit()
    summary = {s: sum(1 for r in out if r["status"] == s) for s in ("change", "same", "error")}
    return {"rows": out, "summary": summary, "applied": apply}
