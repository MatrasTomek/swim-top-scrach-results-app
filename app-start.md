# Uruchamianie swimtop.py

Skrypt pobiera wszystkie starty zawodników z https://www.swimtop.pl/ i dopisuje je do `results.json`.

Wymagania: Python 3.10+, bez dodatkowych bibliotek.

## Uruchomienie

```
python swimtop.py URL_LUB_SLUG [URL_LUB_SLUG ...]
python swimtop.py --file lista.txt
python swimtop.py --file lista.txt URL ... --out inny.json
```

`URL_LUB_SLUG` to miejsce do uzupełnienia, a nawiasy kwadratowe oznaczają „opcjonalnie więcej”. W prawdziwym poleceniu wpisz konkretny adres lub slug, np. `python swimtop.py amelia-was-2012`.

### Windows: „nie znaleziono Python”

Komunikat „nie znaleziono Python; uruchom bez argumentów, aby zainstalować z Microsoft Store” oznacza, że `python` jest tylko skrótem do Microsoft Store.

- Sprawdź launcher: `py --version`. Jeśli działa (3.10 lub nowszy), używaj `py swimtop.py ...` zamiast `python swimtop.py ...`.
- Jeśli `py` też nie działa, zainstaluj Pythona z https://www.python.org/downloads/ i zaznacz „Add python.exe to PATH”, albo wykonaj `winget install Python.Python.3.12`. Potem otwórz nowe okno terminala.
- Jeśli nadal otwiera się Store, wyłącz *Ustawienia → Aplikacje → Zaawansowane ustawienia aplikacji → Aliasy wykonywania aplikacji* dla `python.exe` i `python3.exe`.

- Zawodnika podajesz jako URL profilu (`https://www.swimtop.pl/zawodnik/amelia-was-2012`) albo sam slug (`amelia-was-2012`).
- `--file` to plik z listą, jeden URL lub slug w wierszu. Puste wiersze i wiersze zaczynające się od `#` są pomijane. Można łączyć z argumentami w wierszu poleceń.
- `--out` to plik wynikowy. Domyślnie `results.json` obok skryptu.

Przykład `lista.txt`:

```
https://www.swimtop.pl/zawodnik/amelia-was-2012
https://www.swimtop.pl/zawodnik/hanna-jurek-2013
# ta linia jest ignorowana
```

## Jak to działa

1. Z każdego URL-a wyciąga slug (bez parametrów, końcowego `/` i `www`). Ten sam zawodnik podany kilka razy jest pobierany raz.
2. Pobiera `https://www.swimtop.pl/api/zawodnik/<slug>`, czyli JSON ze wszystkimi startami. Przy błędzie sieci lub 5xx ponawia do 3 razy, a między zawodnikami robi 0,5 s przerwy.
3. Przelicza starty na format `results.json`:
   - `"400 m st. zmiennym"` daje `dystans: "400m"` i `styl: "zmienny"`,
   - data `2026-07-10` daje `10/7/2026`,
   - `konkurencja_nr` i `tor` to `0` (API ich nie podaje),
   - `plec` wynika z płci zawodnika, a `timestamp_pobrania` to czas pobrania (UTC),
   - klucz zawodnika to `nazwisko_imie` małymi literami bez polskich znaków, np. `was_amelia`.
4. Tylko **dopisuje** nowe starty, niczego nie usuwa ani nie zmienia. Start jest duplikatem, gdy zgadzają się data, dystans, styl, basen i czas (`00:00:35.80` i `35.80` to ten sam czas).
   - Zawodnik już w pliku: dopisuje brakujące starty i uzupełnia rok urodzenia, jeśli był pusty. Klub zostaje bez zmian.
   - Zawodnik nowy: tworzy wpis.
   - Imiennik z innym rokiem urodzenia dostaje klucz z rokiem, np. `was_amelia_2012`.
5. Zapisuje plik raz, na końcu, bezpiecznie: przed pierwszym zapisem tworzy `results.json.bak`, zapisuje do pliku tymczasowego i podmienia nim właściwy plik. Przerwanie w trakcie nie uszkodzi danych.

## Wynik i kody wyjścia

Po każdym zawodniku skrypt wypisuje podsumowanie, a na końcu listę niepowodzeń:

```
was_amelia: dopisano 153, pominięto duplikatów 111
Niepowodzenia:
  nieistniejacy-1900: HTTP 404
```

- `0`: wszyscy zawodnicy pobrani.
- `1`: przynajmniej jeden zawodnik się nie udał (pozostali są zapisani).
- `2`: błąd uruchomienia, np. uszkodzony `results.json` albo brak pliku z listą. Nic nie jest zapisywane.

Ponowne uruchomienie z tą samą listą niczego nie zmienia. Dopisują się tylko nowe starty.

## Dobrze wiedzieć

- `results.json.bak` powstaje raz i nie jest nadpisywane, żeby zły pierwszy bieg nie zniszczył kopii oryginału. Żeby je odświeżyć, usuń plik `.bak`.
- API SwimTop nie zwraca startów pośrednich (`Lap`). Stare wpisy `Lap` w pliku zostają nietknięte.
- Dwa identyczne starty (ten sam dzień, dystans, styl, basen i czas, np. eliminacje i finał z tym samym wynikiem) są traktowane jako jeden.

## Testy

```
pip install pytest
python -m pytest
```
