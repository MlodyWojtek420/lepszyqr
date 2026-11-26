import re
import unicodedata
from urllib.parse import urlparse

_PL = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O"})


def slugify(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.translate(_PL))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()


def normalize_name(s: str) -> str:
    return " ".join((s or "").split())


def name_key(first: str, last: str) -> str:
    return f"{normalize_name(first).casefold()}|{normalize_name(last).casefold()}"


def clean_name(value: str, label: str) -> str:
    v = normalize_name(value)
    if not v:
        raise ValueError(f"Brak pola: {label}")
    if len(v) > 100:
        raise ValueError(f"Pole „{label}” jest za długie (max 100 znaków)")
    return v


def validate_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        raise ValueError("Brak adresu URL")
    if len(url) > 2000:
        raise ValueError("Adres URL jest za długi (max 2000 znaków)")
    if re.search(r"\s", url):
        raise ValueError("Adres URL nie może zawierać spacji")
    try:
        p = urlparse(url)
        host = p.hostname
    except ValueError:
        raise ValueError("Niepoprawny adres URL")
    if p.scheme not in ("http", "https") or not host:
        raise ValueError("Adres URL musi zaczynać się od http:// lub https://")
    return url
