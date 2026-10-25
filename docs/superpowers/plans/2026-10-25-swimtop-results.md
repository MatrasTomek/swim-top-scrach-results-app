# swimtop.py Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skrypt CLI pobierający wszystkie starty zawodników z SwimTop i dopisujący je do `results.json`.

**Architecture:** Jeden plik `swimtop.py` z małymi, czystymi funkcjami (parsowanie, mapowanie, merge) oraz cienką warstwą I/O (pobieranie, zapis, CLI). Dane pochodzą z JSON-a `GET /api/zawodnik/<slug>`, a testy działają na zapisanych odpowiedziach.

**Tech Stack:** Python 3.10+, tylko biblioteka standardowa (`urllib`, `json`, `argparse`, `unicodedata`, `re`); `pytest` do testów.

**Spec:** `docs/superpowers/specs/2026-10-25-swimtop-results-design.md`

**Uwaga:** katalog nie jest repozytorium git, więc plan nie ma kroków commit. Jeśli ma być repozytorium, wykonaj `git init` przed Taskiem 1 i commituj po każdym tasku.

## Global Constraints

- Tylko biblioteka standardowa w `swimtop.py`; `pytest` tylko do testów.
- Endpoint: `https://www.swimtop.pl/api/zawodnik/<slug>`, nagłówek `User-Agent`, timeout, do 3 prób przy błędach sieci i 5xx, przerwa 0,5 s między zawodnikami.
- Klucz zawodnika: `nazwisko_imie`, małe litery, bez polskich znaków; kolizja imienników daje przyrostek `_<rok>`.
- `data` jako `d/m/yyyy` bez zer wiodących; `czas` jako `m:ss.cc` lub `ss.cc`; `konkurencja_nr` i `tor` równe `0`; `timestamp_pobrania` w ISO 8601 UTC z `Z`.
- `plec`: `Kobieta` → `Kobiet`, `Mężczyzna` → `Mężczyzn`, inna → `""`.
- Start pośredni (`isSplit`): `styl` z dopiskiem ` Lap`, `punkty: null`.
- Duplikat startu: `(data, dystans, styl, basen, znormalizowany czas)`; nic nie jest usuwane ani nadpisywane; `klub` istniejącego wpisu bez zmian, `rok_urodzenia` uzupełniany tylko gdy `null`.
- Zapis: `results.json.bak`, plik tymczasowy w tym samym katalogu, atomowa zamiana; UTF-8, `ensure_ascii=False`, wcięcie tabulatorem.
- Kod wyjścia 0 tylko gdy wszyscy zawodnicy się udali.

## Review Focus

- Nazwiska z `ł`/`Ł` (NFKD ich nie rozkłada), `ó`, `ż`, dwuczłonowe `Kowalska-Nowak` i spacje: klucz ma być czysty ASCII, ze znakami innymi niż litery i cyfry zamienionymi na pojedyncze `_`.
- Zawodnik bez startów, z `birthYear: null` lub bez `gender`: brak wyjątku, wpis powstaje z `rok_urodzenia: null` i `plec: ""`.
- Uszkodzony lub pusty `results.json`: czytelny błąd, plik niezmieniony i bez `.bak` nadpisującego dobrą kopię.
- Odpowiedź 200, ale nie-JSON (np. strona HTML z błędem): traktowana jak błąd pobrania, nie wyjątek z tracebackiem.
- Ten sam zawodnik podany dwa razy (URL z `?query`, końcowym `/`, bez `www`, sam slug): pobrany raz.

---

### Task 1: Funkcje pomocnicze i fixtures

**Files:**
- Create: `swimtop.py`
- Create: `tests/test_helpers.py`
- Create: `tests/fixtures/amelia-was-2012.json`, `tests/fixtures/franciszek-was-2014.json`

**Interfaces:**
- Produces:
  - `extract_slug(text: str) -> str`
  - `parse_event(event: str) -> tuple[str, str] | None`
  - `normalize_time(t: str) -> str`
  - `format_date(iso: str) -> str`
  - `athlete_key(last: str, first: str) -> str`

- [ ] **Step 1: Pobierz fixtures**

```bash
mkdir -p tests/fixtures
for s in amelia-was-2012 franciszek-was-2014; do curl -s -A "Mozilla/5.0" "https://www.swimtop.pl/api/zawodnik/$s" -o tests/fixtures/$s.json; done
```

Oczekiwane: oba pliki to JSON z kluczem `performances` (264 i 123 pozycje w chwili pisania planu; testy nie mogą zakładać dokładnych liczb).

- [ ] **Step 2: Napisz testy w `tests/test_helpers.py`** (z `sys.path` wskazującym na katalog główny, np. `conftest.py` lub `pytest.ini` z `pythonpath = .`)

```python
def test_extract_slug_variants():
    for s in ["https://www.swimtop.pl/zawodnik/amelia-was-2012",
              "https://swimtop.pl/zawodnik/amelia-was-2012/",
              "https://www.swimtop.pl/zawodnik/amelia-was-2012?tab=meets",
              "amelia-was-2012", "  amelia-was-2012  "]:
        assert extract_slug(s) == "amelia-was-2012"

def test_parse_event():
    assert parse_event("400 m st. zmiennym") == ("400m", "zmienny")
    assert parse_event("50 m st. motylkowym") == ("50m", "motylkowy")
    assert parse_event("100 m st. klasycznym") == ("100m", "klasyczny")
    assert parse_event("4x50 m st. dowolnym") is None

def test_all_fixture_events_parse():   # po jednym teście na oba fixtures
    ...  # każde performance["event"] musi dać wynik != None

def test_normalize_time():
    assert normalize_time("00:00:35.80") == "35.80"
    assert normalize_time("00:02:48.15") == "2:48.15"
    assert normalize_time("1:02.52") == "1:02.52"
    assert normalize_time("35.80") == "35.80"
    assert normalize_time("10:04.22") == "10:04.22"

def test_format_date():
    assert format_date("2026-07-10") == "10/7/2026"
    assert format_date("2025-03-05") == "5/3/2025"

def test_athlete_key():
    assert athlete_key("Wąs", "Amelia") == "was_amelia"
    assert athlete_key("Łukasiewicz", "Żaneta") == "lukasiewicz_zaneta"
    assert athlete_key("Kowalska-Nowak", "Anna Maria") == "kowalska_nowak_anna_maria"
```

- [ ] **Step 3: Uruchom testy i zobacz, że padają**

Run: `python -m pytest tests/test_helpers.py -v`
Expected: FAIL (`ImportError`/`NameError`).

- [ ] **Step 4: Zaimplementuj funkcje w `swimtop.py`**

`extract_slug`: ostatni niepusty segment ścieżki po `/zawodnik/` gdy wejście zawiera `/`, bez query i fragmentu; samo slug zwracane po `strip()`. `parse_event`: regex `^(\d+)\s*m\s+st\.\s+(\w+)$`, mapa końcówek `dowolnym/grzbietowym/klasycznym/motylkowym/zmiennym` na formę podstawową. `normalize_time`: dla postaci `HH:MM:SS.cc` odrzuć godziny równe zero i minuty równe zero (wtedy wynik to `ss.cc`), w przeciwnym razie zapisz jako `m:ss.cc` bez zera wiodącego przy minutach; formaty `m:ss.cc` i `ss.cc` zwracaj bez zmian. `athlete_key`: NFKD, usuń znaki łączące, ręcznie `ł→l`, `Ł→L`, małe litery, ciągi znaków spoza `[a-z0-9]` zamień na jedno `_`, złóż jako `nazwisko_imie`.

- [ ] **Step 5: Uruchom testy**

Run: `python -m pytest tests/test_helpers.py -v`
Expected: PASS.

---

### Task 2: Mapowanie odpowiedzi API na wpis zawodnika

**Files:**
- Modify: `swimtop.py`
- Create: `tests/test_mapping.py`

**Interfaces:**
- Consumes: `parse_event`, `normalize_time`, `format_date`, `athlete_key` z Taska 1.
- Produces:
  - `build_entry(api: dict, fetched_at: str) -> tuple[str, dict, list[str]]` zwraca `(base_key, athlete, warnings)`; `athlete` ma pola `imie`, `nazwisko`, `rok_urodzenia` (`int | None`), `klub`, `starty`.
  - `now_iso() -> str` zwraca czas UTC jako `YYYY-MM-DDTHH:MM:SS.mmmZ`.

- [ ] **Step 1: Napisz testy w `tests/test_mapping.py`**

```python
def test_amelia_entry():
    key, a, warns = build_entry(load("amelia-was-2012"), "2026-10-25T10:00:00.000Z")
    assert key == "was_amelia"
    assert (a["imie"], a["nazwisko"], a["rok_urodzenia"]) == ("Amelia", "Wąs", 2012)
    assert len(a["starty"]) == len(load("amelia-was-2012")["performances"])
    first = a["starty"][0]
    assert set(first) == {"zawody","data","miejscowosc","basen","konkurencja_nr","dystans",
                          "styl","plec","tor","czas","punkty","timestamp_pobrania"}
    assert first["konkurencja_nr"] == 0 and first["tor"] == 0
    assert first["plec"] == "Kobiet"
    assert first["timestamp_pobrania"] == "2026-10-25T10:00:00.000Z"

def test_known_first_start():  # pierwszy performance Amelii: 400 m zmiennym, 5:21.33, Olsztyn
    ...  # dystans "400m", styl "zmienny", basen "50m", czas "5:21.33", punkty 552, data "10/7/2026",
         # zawody "Letnie Mistrzostwa Polski Juniorow Młodszych 14 Lat W Pływaniu"

def test_split_start_gets_lap_suffix_and_null_points():
    api = minimal_api(perf(isSplit=True, event="50 m st. dowolnym", points=None, time="31.25"))
    _, a, _ = build_entry(api, TS)
    assert a["starty"][0]["styl"] == "dowolny Lap" and a["starty"][0]["punkty"] is None

def test_unknown_event_is_skipped_with_warning():
    api = minimal_api(perf(event="4x50 m st. dowolnym"))
    _, a, warns = build_entry(api, TS)
    assert a["starty"] == [] and len(warns) == 1

def test_missing_optional_fields():   # birthYear None, bez gender, bez performances
    _, a, _ = build_entry({"found": True, "user": {"firstName": "A", "lastName": "B"}, "performances": []}, TS)
    assert a["rok_urodzenia"] is None and a["starty"] == []

def test_gender_mapping():  # "Mężczyzna" -> "Mężczyzn", nieznana wartość -> ""
```

`load`, `minimal_api`, `perf` to lokalne helpery testowe (`perf` zwraca słownik startu z polami jak w API, wartości domyślne ważne).

- [ ] **Step 2: Uruchom testy i zobacz, że padają**

Run: `python -m pytest tests/test_mapping.py -v`
Expected: FAIL.

- [ ] **Step 3: Zaimplementuj `build_entry` i `now_iso` w `swimtop.py`**

`rok_urodzenia` to `int(birthYear)` albo `None`, gdy brak lub nieliczbowy. `zawody` to `meet.title` lub `""`, gdy `meet` brak. Ostrzeżenie dla pominiętej konkurencji zawiera slug lub nazwisko i tekst `event`.

- [ ] **Step 4: Uruchom testy**

Run: `python -m pytest tests/test_mapping.py -v`
Expected: PASS.

---

### Task 3: Merge, dedup i bezpieczny zapis

**Files:**
- Modify: `swimtop.py`
- Create: `tests/test_merge.py`

**Interfaces:**
- Consumes: `normalize_time` (Task 1) oraz struktura `athlete` z `build_entry` (Task 2).
- Produces:
  - `load_db(path: str) -> dict` zwraca `{}` gdy plik nie istnieje; dla pustego lub uszkodzonego JSON-a rzuca `DbError` (podklasa `Exception`, komunikat zawiera ścieżkę).
  - `merge_athlete(db: dict, base_key: str, athlete: dict) -> tuple[str, int, int]` modyfikuje `db` i zwraca `(użyty_klucz, dopisane, pominięte)`.
  - `save_db(path: str, db: dict) -> None`.

- [ ] **Step 1: Napisz testy w `tests/test_merge.py`**

```python
def test_new_athlete_added():
def test_second_run_adds_nothing():      # merge dwa razy ten sam wpis: (k, 0, N) za drugim razem
def test_old_format_time_counts_as_duplicate():
    # w db start z czasem "00:00:35.80", nowy z "35.80" ta sama data/dystans/styl/basen -> pominięty
def test_old_entries_untouched_including_lap():
    # w db start "dowolny Lap" z punkty None i zawody "" pozostaje bez zmian po merge
def test_club_kept_year_filled_when_null():
    # istniejący klub "A", nowy "B" -> "A"; rok None -> uzupełniony; rok 2013 -> bez zmian
def test_namesake_gets_year_suffix():
    # db["was_amelia"]["rok_urodzenia"] == 2010, nowy 2012 -> klucz "was_amelia_2012"
def test_namesake_reuses_suffixed_key():
    # db ma już "was_amelia" (2010) i "was_amelia_2012" -> merge do drugiego
def test_load_db_missing_returns_empty / test_load_db_corrupt_raises(tmp_path):
def test_save_db_writes_bak_and_tab_indent(tmp_path):
    # po zapisie istnieje results.json.bak z poprzednią treścią, plik używa "\t", znaki polskie nie są \u-escapowane
def test_save_db_failure_leaves_original(tmp_path, monkeypatch):
    # wymuszony błąd przy os.replace -> oryginał niezmieniony
```

- [ ] **Step 2: Uruchom testy i zobacz, że padają**

Run: `python -m pytest tests/test_merge.py -v`
Expected: FAIL.

- [ ] **Step 3: Zaimplementuj `DbError`, `load_db`, `merge_athlete`, `save_db`**

Wybór klucza: jeśli `base_key` nie istnieje w `db`, użyj go. Jeśli istnieje, a jego `rok_urodzenia` jest `None` lub równy nowemu (albo nowy jest `None`), użyj go. W przeciwnym razie użyj `f"{base_key}_{rok}"` (to samo reguły dla ewentualnego istniejącego klucza z przyrostkiem). Duplikat to start, którego `(data, dystans, styl, basen, normalize_time(czas))` jest już na liście; klucze dopisanych startów dodawaj do zbioru, żeby duplikaty wewnątrz jednej odpowiedzi też się nie powtarzały (zgodnie ze spec dwa takie same starty z jednej odpowiedzi to jeden start). `save_db`: jeśli plik istnieje, skopiuj go do `<path>.bak`; zapisz do `tempfile.NamedTemporaryFile(dir=<katalog pliku>, delete=False)`, następnie `os.replace`; przy wyjątku usuń plik tymczasowy i przepuść wyjątek.

- [ ] **Step 4: Uruchom testy**

Run: `python -m pytest tests/test_merge.py -v`
Expected: PASS.

---

### Task 4: Pobieranie i CLI

**Files:**
- Modify: `swimtop.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: wszystkie funkcje z Tasków 1-3.
- Produces:
  - `class FetchError(Exception)`
  - `fetch_athlete(slug: str, *, opener=urllib.request.urlopen, retries: int = 3, sleep=time.sleep) -> dict` zwraca zdekodowany JSON, rzuca `FetchError` dla błędu sieci po wyczerpaniu prób, 404, odpowiedzi nie-JSON lub `found: false`.
  - `collect_slugs(args: list[str], file: str | None) -> list[str]` zwraca unikalne slugi w kolejności podania.
  - `main(argv: list[str] | None = None, *, fetch=fetch_athlete, sleep=time.sleep) -> int`.

- [ ] **Step 1: Napisz testy w `tests/test_cli.py`**

```python
def test_collect_slugs_dedups_and_skips_comments(tmp_path):
    # plik: "# komentarz", "", URL z ?query, ten sam slug bez www, inny slug; argument pozycyjny powtarza slug
    # -> każdy slug raz, w kolejności pierwszego wystąpienia
def test_fetch_retries_on_5xx_then_succeeds():     # opener rzuca HTTPError 503 dwa razy, potem zwraca JSON
def test_fetch_404_no_retry_raises():
def test_fetch_html_body_raises_fetcherror():      # 200 z "<html>..." 
def test_fetch_found_false_raises():
def test_main_merges_two_athletes_and_returns_0(tmp_path):   # fetch podstawione fixtures, wynik w results.json
def test_main_continues_after_failure_and_returns_nonzero(tmp_path, capsys):
    # pierwszy slug rzuca FetchError, drugi działa -> drugi zapisany, kod != 0, stdout zawiera nieudany slug
def test_main_corrupt_db_exits_nonzero_without_writing(tmp_path, capsys):
def test_main_summary_lists_added_and_skipped(tmp_path, capsys):   # drugi przebieg: "0" dopisanych
```

- [ ] **Step 2: Uruchom testy i zobacz, że padają**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL.

- [ ] **Step 3: Zaimplementuj `FetchError`, `fetch_athlete`, `collect_slugs`, `main` i blok `if __name__ == "__main__"`**

`fetch_athlete`: `Request` z `User-Agent` (np. `Mozilla/5.0 swimtop-script`) i `timeout=30`; ponowienia (z rosnącą przerwą) tylko dla `URLError`, timeoutu i `HTTPError` 5xx; 4xx kończy od razu. `main` używa `argparse` (pozycyjne `inputs` z `nargs="*"`, `--file`, `--out` z domyślną ścieżką `results.json` obok skryptu); brak jakichkolwiek wejść to błąd użycia. Kolejność: `load_db` (błąd `DbError` zwraca niezerowy kod przed jakimkolwiek zapisem), pętla po slugach z `sleep(0.5)` między nimi, `save_db` raz na końcu (gdy cokolwiek się powiodło), podsumowanie na stdout.

- [ ] **Step 4: Uruchom całość testów**

Run: `python -m pytest -v`
Expected: PASS (wszystkie testy z Tasków 1-4).

---

### Task 5: Test na żywo

**Files:** brak zmian w kodzie; używa kopii pliku.

- [ ] **Step 1: Uruchom na kopii danych**

```bash
cp results.json /tmp/results-live.json
python swimtop.py https://www.swimtop.pl/zawodnik/franciszek-was-2014 https://www.swimtop.pl/zawodnik/hanna-jurek-2013 https://www.swimtop.pl/zawodnik/amelia-was-2012 --out /tmp/results-live.json
```

Oczekiwane: kod wyjścia 0; w podsumowaniu `was_franciszek` i `jurek_hanna` mają dopisane starty oraz pominięte duplikaty (stare wpisy Franciszka mieszczą się w pierwszym przebiegu jako duplikaty tam, gdzie czas i data się zgadzają), `was_amelia` jest nowym wpisem; istnieje `/tmp/results-live.json.bak`; stare wpisy `dowolny Lap` nadal są w pliku.

- [ ] **Step 2: Uruchom to samo drugi raz**

Oczekiwane: dla każdego zawodnika 0 dopisanych startów.

- [ ] **Step 3: Sprawdź błąd**

Run: `python swimtop.py nieistniejacy-zawodnik-1900 --out /tmp/results-live.json; echo $?`
Expected: komunikat o niepowodzeniu na stdout i kod wyjścia różny od 0; plik wyjściowy bez zmian.

- [ ] **Step 4: Porównaj z dotychczasowym `results.json` bez nadpisywania go**

Poinformuj użytkownika o wynikach i zapytaj, czy skrypt ma zapisywać już do prawdziwego `results.json`.
