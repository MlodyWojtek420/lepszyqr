import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .db import get_db
from .files import photo_path
from .models import Volunteer

router = APIRouter(prefix="/api/export")


def _check_key(x_api_key: str | None) -> None:
    if not config.EXPORT_API_KEY:
        raise HTTPException(404)
    if not x_api_key or not hmac.compare_digest(x_api_key.encode(), config.EXPORT_API_KEY.encode()):
        raise HTTPException(401, "Niepoprawny klucz API")


@router.get("/volunteers")
def export_volunteers(x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Minimalny eksport dla strony weryfikacyjnej (tylko odczyt, klucz API)."""
    _check_key(x_api_key)
    return [
        {"id": v.id, "first_name": v.first_name, "last_name": v.last_name,
         "status": v.status, "url": v.url, "photo": f"/api/export/volunteers/{v.id}/photo"}
        for v in db.scalars(select(Volunteer).order_by(Volunteer.id))
    ]


@router.get("/volunteers/{vid}/photo")
def export_photo(vid: int, x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    p = photo_path(vid)
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")
