# Identyfikatory wolontariuszy (qr gen)

Prosta aplikacja webowa do zarządzania wolontariuszami i generowania identyfikatorów PDF
ze zdjęciem, imieniem, nazwiskiem i indywidualnym kodem QR (bezpośredni adres URL strony weryfikacyjnej).

**Stack:** FastAPI (Python 3.12) · React (Vite) · PostgreSQL 16 · Playwright/Chromium (PDF) · Docker Compose (Dockge).

---

## 1. Wymagania

- Serwer z **Dockge** (Docker + Docker Compose v2.22 lub nowszy).
- Repozytorium **Git** (GitHub, GitLab, Gitea…) na kod aplikacji – najlepiej prywatne. Serwer musi mieć do niego dostęp.
- Dostęp do internetu **podczas budowania** obrazów (pakiety, Chromium); pierwsze budowanie trwa 5–10 min.
- ok. 2 GB RAM na kontenery oraz miejsce na zdjęcia i kopie zapasowe.

## 2. Wdrożenie w Dockge (krok po kroku)

Całość robisz w przeglądarce – nie musisz logować się na serwer.

**Krok 1 – kod do repozytorium.** Utwórz repozytorium (np. `qr-gen`) i wgraj do niego zawartość tego projektu
(`compose.yaml`, `backend/`, `frontend/`, `README.md`, `.env.example`, `.gitignore`). Plik `.env` nie trafia do repozytorium.
Dla repozytorium prywatnego utwórz token dostępu tylko do odczytu (GitHub: *Fine-grained token → Contents: Read*).

**Krok 2 – nowy stack w Dockge.**
1. Kliknij **+ Compose**, nazwij stack `qr-gen`.
2. W polu YAML wklej całą zawartość pliku `compose.yaml`.
3. W polu `.env` wklej zawartość `.env.example` i uzupełnij:
   - `REPO_URL` – adres repozytorium (dla prywatnego: `https://UZYTKOWNIK:TOKEN@github.com/ORG/qr-gen.git`),
   - `REPO_REF` – gałąź (domyślnie `main`),
   - `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, `SECRET_KEY` – własne, silne wartości.

**Krok 3 – uruchomienie.** Kliknij **Deploy**. Dockge pobierze kod z repozytorium, zbuduje obrazy i uruchomi 4 kontenery
(`db`, `backend`, `frontend`, `backup`). Postęp zobaczysz w oknie logów Dockge.

**Krok 4 – logowanie.** Otwórz `http://ADRES_SERWERA:8080` i zaloguj się danymi `ADMIN_USER` / `ADMIN_PASSWORD`.

Dane (baza, zdjęcia, kopie) trafiają do katalogów `data/` i `backups/` wewnątrz katalogu stacku
(domyślnie `/opt/stacks/qr-gen/`). Dockge musi mieć skonfigurowany ten sam ścieżkowy katalog stacków po stronie hosta
i kontenera (domyślna instalacja Dockge tak ma).

### Co ustawić w `.env`

| Zmienna | Opis |
|---|---|
| `REPO_URL`, `REPO_REF` | Repozytorium z kodem i gałąź/tag do zbudowania. |
| `POSTGRES_PASSWORD` | Długie losowe hasło (tylko litery i cyfry). |
| `ADMIN_USER`, `ADMIN_PASSWORD` | Dane logowania do panelu. |
| `SECRET_KEY` | Losowy ciąg (min. 32 znaki). Zmiana wylogowuje wszystkich. |
| `HTTP_PORT` | Port panelu (domyślnie 8080). |
| `COOKIE_SECURE` | `true`, gdy panel jest dostępny przez HTTPS (zalecane). |
| `EXPORT_API_KEY` | Opcjonalnie – patrz sekcja 7. Puste = wyłączone. |
| `BACKUP_KEEP_DAYS` | Ile dni trzymać kopie zapasowe (domyślnie 30). |

## 3. HTTPS (zalecane)

Panel przesyła hasło i dane osobowe – wystaw go przez HTTPS za reverse proxy. Przykład z Caddy
(certyfikat Let's Encrypt wystawia się sam), `Caddyfile`:

```
panel.organizacja.pl {
    reverse_proxy localhost:8080
}
```

Po uruchomieniu HTTPS ustaw w `.env` `COOKIE_SECURE=true` i kliknij Deploy w Dockge.
Jeśli panel ma być dostępny tylko w sieci wewnętrznej/VPN, ogranicz port zaporą sieciową.

## 4. Pierwsze kroki w panelu

1. Zakładka **Szablon identyfikatora** – ustaw nazwę organizacji, kolory, logo, rozmiar karty
   (domyślnie 54×86 mm, pionowo) i układ PDF. Przycisk „Zapisz i pokaż podgląd PDF” pokazuje przykład.
2. **Dodaj wolontariusza** (zakładka Wolontariusze) albo zaimportuj listę (zakładka Import z Excela).
3. Zaznacz osoby na liście → **Identyfikatory PDF**. Bez zaznaczenia przycisk generuje PDF dla wszystkich widocznych osób
   (po zastosowaniu wyszukiwania/filtra statusu).

### Układy PDF
- **Arkusze A4** – kilka identyfikatorów na stronie (domyślnie 9 sztuk 54×86 mm) z liniami cięcia. Najszybsze i najtańsze w druku.
- **Jedna karta na stronę** – strona ma dokładnie rozmiar karty; do drukarek kart plastikowych.

## 5. Import z Excela i ZIP

Plik `.xlsx` z nagłówkami w pierwszym wierszu (wzór pobierzesz w panelu):

| first_name | last_name | photo | url |
|---|---|---|---|
| Jan | Kowalski | jan.jpg | https://organizacja.pl/wolontariusze/jan-kowalski |

- Do ZIP wrzuć zdjęcia o nazwach zgodnych z kolumną `photo` (wielkość liter bez znaczenia, podfoldery dozwolone).
  **Unikaj polskich znaków w nazwach plików** – archiwa tworzone w Windows często kodują je niepoprawnie.
- Zdjęcia: JPG/PNG/WEBP do 10 MB; system przycina je do kadru 3:4 i zmniejsza do 600×800 px.
- Przebieg: wgranie → **podgląd z walidacją** (błędy, brakujące zdjęcia, złe URL, duplikaty) → zatwierdzenie.
- **Duplikaty** rozpoznawane są po imieniu i nazwisku (bez względu na wielkość liter). Osoby już istniejące są domyślnie pomijane;
  możesz wybrać „zaktualizuj adres URL i zdjęcie”. Ponowny import tego samego pliku nie tworzy kopii.
- Ręczne dodanie osoby o istniejącym imieniu i nazwisku wymaga potwierdzenia (to mogą być dwie różne osoby).

### Zmiana adresów URL
- pojedynczo: w liście kliknij **zmień** przy adresie,
- wiele osób: zaznacz je → **Zmień adresy URL** → „Zamień fragment” (np. zmiana domeny) lub „Wzorzec adresu”
  (np. `https://organizacja.pl/wolontariusze/{slug}`), zawsze z podglądem przed zapisem,
- z Excela: zakładka Import → „Import nowych adresów URL” (kolumna `url` + `id` albo `first_name` i `last_name`).

Każda zmiana adresu **automatycznie odświeża kod QR w systemie**. Pamiętaj, że **już wydrukowane identyfikatory
zachowują stary kod QR** – dla zmienionych osób trzeba wydrukować nowe.
Kody QR możesz też pobrać jako PNG (zaznacz osoby → „Pobierz kody QR (ZIP)”) albo odświeżyć zbiorczo.

## 6. Kopie zapasowe i przywracanie

Kontener `backup` w stacku co 24 h zapisuje w `backups/` (w katalogu stacku) dwa pliki:
`db-DATA.sql.gz` (baza) i `files-DATA.tar.gz` (zdjęcia, kody QR, szablon, logo). Pierwsza kopia powstaje zaraz po uruchomieniu.
Starsze niż `BACKUP_KEEP_DAYS` dni są usuwane. **Kopiuj katalog `backups/` także poza serwer** (inny dysk/serwer/chmura) –
kopia na tym samym dysku nie chroni przed awarią dysku.

**Przywracanie** (w Dockge):
1. Zatrzymaj kontener `backend` (lub cały stack, a potem uruchom tylko `db` i `backup`).
2. Otwórz terminal kontenera `backup` (zakładka Terminal/Shell kontenera w Dockge) i wykonaj, podstawiając właściwe daty:
   ```sh
   ls /backups
   gunzip -c /backups/db-20250101-023000.sql.gz | psql
   rm -rf /data/photos /data/qr
   tar -xzf /backups/files-20250101-023000.tar.gz -C /data
   ```
3. Uruchom ponownie `backend`.

## 7. Strona weryfikacyjna (poza aplikacją)

Zgodnie z założeniami strona, na którą prowadzi QR, jest na witrynie organizacji. Żeby mogła pokazać aktualny
**status**, zdjęcie i imię/nazwisko, aplikacja ma opcjonalny, tylko-do-odczytu endpoint eksportu.
Włącz go ustawiając `EXPORT_API_KEY` w `.env` (Deploy w Dockge):

```bash
curl -H "X-API-Key: TWOJ_KLUCZ" https://panel.organizacja.pl/api/export/volunteers
# -> [{"id":1,"first_name":"Jan","last_name":"Kowalski","status":"active","url":"https://...","photo":"/api/export/volunteers/1/photo"}, ...]
```

Zdjęcie: `GET /api/export/volunteers/{id}/photo` z tym samym nagłówkiem. Strona organizacji powinna pobierać dane
po stronie serwera (klucz nie może trafić do przeglądarki), a wolontariusza dopasować po polu `url`.
Publiczna strona powinna pokazywać tylko niezbędne minimum: zdjęcie, imię i nazwisko, status.
Jeśli nie chcesz używać eksportu, zostaw `EXPORT_API_KEY` pusty – endpoint zwróci wtedy 404.

## 8. Aktualizacje i obsługa

- **Aktualizacja aplikacji:** wgraj zmiany do repozytorium Git, potem w Dockge kliknij **Deploy** (lub *Update*) przy stacku –
  obrazy `backend` i `frontend` są przebudowywane z najnowszego kodu (`pull_policy: build`). Dane zostają.
- **Logi:** w Dockge otwórz stack i wybierz logi kontenera (`backend`, `frontend`, `db`, `backup`).
- **Restart:** przyciski Restart/Stop/Start przy stacku lub kontenerze.
- **Zmiana hasła administratora:** edytuj `.env` w Dockge i kliknij Deploy.
- Wygląd identyfikatora poza ustawieniami z panelu możesz zmienić w repozytorium, w pliku `backend/app/templates/badge.html.j2`
  (HTML + CSS), a następnie zrobić Deploy.

## 9. Bezpieczeństwo – co jest wbudowane

- logowanie administratora (sesja w ciasteczku HttpOnly, 12 h), limit nieudanych prób logowania,
- walidacja zdjęć (format, rozmiar, rzeczywista zawartość obrazu), ZIP (limity rozmiaru) i adresów URL (tylko http/https),
- zdjęcia i kody QR dostępne wyłącznie po zalogowaniu; poza aplikacją wychodzą tylko dane z opcjonalnego eksportu z kluczem API,
- baza i pliki nie są wystawione na zewnątrz – publiczny jest wyłącznie port panelu.

## 10. Rozwiązywanie problemów

| Objaw | Co sprawdzić |
|---|---|
| Panel się nie ładuje | stan i logi kontenerów w Dockge |
| Backend restartuje się | brak/niepoprawne zmienne w `.env` (logi kontenera `backend` w Dockge) |
| Nie można się zalogować przez HTTP | ustaw `COOKIE_SECURE=false`, gdy nie używasz HTTPS |
| PDF generuje się wolno przy tysiącach osób | generuj partiami (np. po 500) lub zwiększ RAM |
| Brak polskich znaków w PDF | kontener ma fonty DejaVu/Liberation – zmień `REPO_REF` na nowy tag/commit lub zrób nowy commit w repozytorium i Deploy (wymusza przebudowę) |
| Import: „Nie znaleziono zdjęcia” | sprawdź nazwy w kolumnie `photo` i w ZIP (bez polskich znaków, z rozszerzeniem) |

## 11. Struktura projektu

```
compose.yaml           – db (PostgreSQL), backend (FastAPI), frontend (nginx + React), backup
.env.example           – wzór zmiennych do wklejenia w Dockge
backend/app/           – API: wolontariusze, import, PDF, szablon, logowanie
backend/app/templates/ – badge.html.j2 (wygląd identyfikatora)
frontend/src/          – panel administracyjny (React)
data/ , backups/       – (tworzone automatycznie w katalogu stacku) baza, pliki, kopie
```

## 12. Zakres (MVP)

Zgodnie z założeniami nie ma UUID, resolverów ani przekierowań, wielopoziomowych uprawnień ani statystyk.
Jeden administrator (z `.env`); zmiana hasła = edycja `.env` i Deploy w Dockge.
