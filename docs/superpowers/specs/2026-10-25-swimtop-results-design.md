# swimtop.py — pobieranie startów zawodników z SwimTop

Data: 2026-10-25

## Cel

Skrypt przyjmuje listę adresów profili zawodników (`https://www.swimtop.pl/zawodnik/<slug>`, nawet kilkadziesiąt naraz) i dla każdego pobiera wszystkie starty z wynikami. Dane trafiają do `results.json` w istniejącym formacie, bez naruszania wcześniejszych wpisów.

Kryterium sukcesu: kompletne starty dla wszystkich podanych zawodników, brak duplikatów po ponownym uruchomieniu, jasne podsumowanie nieudanych pobrań.

## Źródło danych

Strona profilu to aplikacja Next.js, a lista startów pochodzi z publicznego JSON-a:

`GET https://www.swimtop.pl/api/zawodnik/<slug>`

Wykorzystywane pola odpowiedzi:
- `found` (bool), `user.firstName`, `user.lastName`, `user.birthYear`, `user.gender`, `user.club`
- `performances[]`: `event` (np. `"400 m st. zmiennym"`), `pool` (`"25m"`/`"50m"`), `time` (`"5:21.33"`), `points` (int), `date` (`YYYY-MM-DD`), `city`, `isSplit`, `meet.title`

Przycisk „Pobierz CSV” na stronie zwraca tylko rekordy życiowe, więc nie jest używany. Wyszukiwarka `GET /api/search?q=` nie jest potrzebna.

Uwaga: w próbce 3 zawodników (607 startów) `isSplit` nigdy nie było `true`. Starty `dowolny Lap` ze starszych danych nie pochodzą z SwimTop.

## Interfejs

```
python swimtop.py URL_LUB_SLUG [URL_LUB_SLUG ...]
python swimtop.py --file lista.txt
python swimtop.py --file lista.txt URL ... --out results.json
```

- `--file`: jeden URL lub slug w wierszu, puste wiersze i wiersze zaczynające się od `#` są pomijane. Można łączyć z argumentami pozycyjnymi.
- `--out`: domyślnie `results.json` obok skryptu.
- Slug to ostatni segment ścieżki (`/zawodnik/<slug>`); samo `<slug>` też jest akceptowane. Parametry i końcowy `/` ignorowane.
- Kod wyjścia 0 gdy wszystko się udało, niezerowy gdy którykolwiek zawodnik się nie powiódł.

## Przepływ

1. Wczytaj istniejący `results.json` (brak pliku = pusty słownik).
2. Dla każdego sluga: pobierz JSON (`User-Agent`, timeout, do 3 prób przy błędach sieci i 5xx), przerwa ok. 0,5 s między zawodnikami.
3. Zamapuj odpowiedź na wpis zawodnika, dołącz nowe starty (patrz niżej).
4. Zawodnik z `found: false`, 404 lub błędem sieci trafia do listy niepowodzeń i nie przerywa reszty.
5. Zapis: kopia `results.json.bak`, zapis do pliku tymczasowego w tym samym katalogu, atomowa zamiana. Plik zapisywany jako UTF-8, `ensure_ascii=False`, wcięcie tabulatorem (jak w obecnym pliku).
6. Podsumowanie na stdout: dla każdego zawodnika liczba dopisanych i pominiętych (duplikaty) startów, na końcu lista niepowodzeń.

## Mapowanie

Klucz zawodnika: `nazwisko_imie`, małe litery, bez polskich znaków (np. `was_amelia`). Gdy klucz już istnieje, a `rok_urodzenia` zapisanego wpisu jest ustawiony i różni się od pobranego (imiennik), klucz otrzymuje przyrostek `_<rok>` (`was_amelia_2012`).

Wpis zawodnika: `imie`, `nazwisko`, `rok_urodzenia` (int z `birthYear`), `klub`, `starty`.
Dla istniejącego wpisu: `klub` bez zmian, `rok_urodzenia` uzupełniany tylko gdy `null`.

Start:

| Pole | Źródło |
|---|---|
| `zawody` | `meet.title` (pusty string, gdy brak) |
| `data` | `date` jako `d/m/yyyy` bez zer wiodących |
| `miejscowosc` | `city` w oryginalnej pisowni z API |
| `basen` | `pool` (`25m`/`50m`) |
| `konkurencja_nr` | `0` |
| `dystans` | z `event`, np. `400m` |
| `styl` | z `event`: `dowolny`, `grzbietowy`, `klasyczny`, `motylkowy`, `zmienny`; dla `isSplit` dopisek ` Lap` |
| `plec` | z płci zawodnika: `Kobieta` → `Kobiet`, `Mężczyzna` → `Mężczyzn`; nieznana → `""` |
| `tor` | `0` |
| `czas` | `time` w formacie `m:ss.cc` / `ss.cc` |
| `punkty` | `points` (`null` dla startów pośrednich) |
| `timestamp_pobrania` | czas pobrania, ISO 8601 UTC z `Z` |

Konkurencja, której nie da się sparsować do dystansu i stylu, daje ostrzeżenie i pomija ten start; nie przerywa przetwarzania zawodnika.

## Duplikaty

Klucz startu: `(data, dystans, styl, basen, znormalizowany czas)`. Normalizacja czasu usuwa zera wiodące i sprowadza `00:00:35.80` oraz `35.80` do `35.80`, a `00:02:48.15` do `2:48.15`. Start, którego klucz już jest na liście zawodnika, nie jest dopisywany. Nowe starty trafiają na koniec listy. Nic nie jest usuwane ani nadpisywane. Konsekwencja: dwa starty z identycznym czasem tego samego dnia, na tym samym dystansie, stylu i basenie (np. eliminacje i finał) są traktowane jako jeden.

## Testy

`pytest`, bez sieci, na zapisanych odpowiedziach API (fixture):
- wyciąganie sluga z URL-a i z samego sluga
- parsowanie wszystkich konkurencji z próbki (16 konkurencji Amelii) i konkurencja nieznana
- normalizacja czasu i formatu daty
- generowanie klucza zawodnika, w tym polskie znaki i kolizja imienników
- merge na pliku w formacie `results.json`: dopisanie nowych startów, brak duplikatów przy ponownym uruchomieniu, zachowanie starych wpisów (także `Lap`), uzupełnienie `rok_urodzenia`
- obsługa `found: false`, błędu sieci i niezerowego kodu wyjścia
- bezpieczny zapis (kopia `.bak`, brak uszkodzenia pliku przy błędzie)

Dodatkowo jeden ręczny test na żywo z 2–3 zawodnikami.

## Poza zakresem

Wyszukiwanie zawodnika po nazwisku, pobieranie rekordów życiowych, rankingi, czasy międzyczasowe (splity w sensie 50 m/100 m), równoległe pobieranie.

## Struktura plików

```
swimtop.py
tests/test_swimtop.py
tests/fixtures/*.json
results.json
```
