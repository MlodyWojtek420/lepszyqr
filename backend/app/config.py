import os
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
PHOTOS_DIR = DATA_DIR / "photos"
QR_DIR = DATA_DIR / "qr"
TMP_DIR = DATA_DIR / "tmp"
TEMPLATE_FILE = DATA_DIR / "template.json"
LOGO_FILE = DATA_DIR / "logo.png"

DATABASE_URL = os.environ["DATABASE_URL"]
SECRET_KEY = os.environ["SECRET_KEY"]
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
EXPORT_API_KEY = os.getenv("EXPORT_API_KEY", "")

SESSION_HOURS = 12
MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_XLSX_BYTES = 20 * 1024 * 1024
MAX_ZIP_BYTES = 300 * 1024 * 1024
MAX_ZIP_UNCOMPRESSED = 1024 * 1024 * 1024
MAX_IMPORT_ROWS = 5000

STATUSES = ("active", "inactive")


def ensure_dirs() -> None:
    for d in (PHOTOS_DIR, QR_DIR, TMP_DIR / "import"):
        d.mkdir(parents=True, exist_ok=True)
