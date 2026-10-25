#!/usr/bin/env python3
"""Pobiera wszystkie starty zawodników z SwimTop i dopisuje je do results.json."""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

STYLES = {
    "dowolnym": "dowolny",
    "grzbietowym": "grzbietowy",
    "klasycznym": "klasyczny",
    "motylkowym": "motylkowy",
    "zmiennym": "zmienny",
}
EVENT_RE = re.compile(r"^(\d+)\s*m\s+st\.\s+(\w+)$")


def extract_slug(text):
    text = text.strip()
    if "/" not in text:
        return text.split("?")[0].split("#")[0]
    segments = [s for s in urlparse(text).path.split("/") if s]
    if "zawodnik" in segments:
        i = segments.index("zawodnik")
        if i + 1 < len(segments):
            return segments[i + 1]
    return segments[-1] if segments else ""


def parse_event(event):
    m = EVENT_RE.match(event.strip())
    if not m or m.group(2) not in STYLES:
        return None
    return f"{m.group(1)}m", STYLES[m.group(2)]


def normalize_time(t):
    parts = t.split(":")
    if len(parts) == 3:
        h, m, s = int(parts[0]), int(parts[1]), parts[2]
        if h:
            return f"{h}:{m:02d}:{s}"
        parts = [str(m), s]
    if len(parts) == 2:
        m = int(parts[0])
        return f"{m}:{parts[1]}" if m else parts[1]
    return t


def format_date(iso):
    y, m, d = iso.split("-")
    return f"{int(d)}/{int(m)}/{y}"


def athlete_key(last, first):
    def clean(text):
        text = text.replace("ł", "l").replace("Ł", "L")
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")

    return f"{clean(last)}_{clean(first)}"


GENDERS = {"Kobieta": "Kobiet", "Mężczyzna": "Mężczyzn"}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def build_entry(api, fetched_at):
    user = api.get("user") or {}
    first, last = user.get("firstName") or "", user.get("lastName") or ""
    try:
        birth_year = int(user.get("birthYear"))
    except (TypeError, ValueError):
        birth_year = None
    plec = GENDERS.get(user.get("gender"), "")
    starts, warnings = [], []
    for p in api.get("performances") or []:
        if not isinstance(p, dict) or not p.get("date") or not p.get("time"):
            warnings.append(f"{first} {last}: pominięto niekompletny start {p!r}")
            continue
        parsed = parse_event(p.get("event") or "")
        if parsed is None:
            warnings.append(f"{first} {last}: pominięto nieznaną konkurencję {p.get('event')!r}")
            continue
        distance, style = parsed
        split = bool(p.get("isSplit"))
        starts.append({
            "zawody": (p.get("meet") or {}).get("title") or "",
            "data": format_date(p["date"]),
            "miejscowosc": p.get("city") or "",
            "basen": p.get("pool") or "",
            "konkurencja_nr": 0,
            "dystans": distance,
            "styl": f"{style} Lap" if split else style,
            "plec": plec,
            "tor": 0,
            "czas": p["time"],
            "punkty": None if split else p.get("points"),
            "timestamp_pobrania": fetched_at,
        })
    athlete = {
        "imie": first,
        "nazwisko": last,
        "rok_urodzenia": birth_year,
        "klub": user.get("club") or "",
        "starty": starts,
    }
    return athlete_key(last, first), athlete, warnings


class DbError(Exception):
    pass


def load_db(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            db = json.load(f)
    except (OSError, ValueError) as e:
        raise DbError(f"Nie można wczytać {path}: {e}") from e
    if not isinstance(db, dict):
        raise DbError(f"Nieprawidłowa zawartość {path}: oczekiwano obiektu JSON")
    return db


def _start_id(start):
    time_ = start.get("czas")
    return (start.get("data"), start.get("dystans"), start.get("styl"), start.get("basen"),
            normalize_time(str(time_)) if time_ else "")


def merge_athlete(db, base_key, athlete):
    year = athlete["rok_urodzenia"]
    key = base_key
    existing = db.get(key)
    if existing is not None:
        old_year = existing.get("rok_urodzenia")
        if not (old_year is None or year is None or old_year == year):
            key = f"{base_key}_{year}"
    target = db.setdefault(key, {
        "imie": athlete["imie"],
        "nazwisko": athlete["nazwisko"],
        "rok_urodzenia": year,
        "klub": athlete["klub"],
        "starty": [],
    })
    target.setdefault("starty", [])
    if target.get("rok_urodzenia") is None:
        target["rok_urodzenia"] = year
    seen = {_start_id(s) for s in target["starty"]}
    added = skipped = 0
    for start in athlete["starty"]:
        sid = _start_id(start)
        if sid in seen:
            skipped += 1
            continue
        seen.add(sid)
        target["starty"].append(start)
        added += 1
    return key, added, skipped


def save_db(path, db):
    if os.path.exists(path) and not os.path.exists(path + ".bak"):
        shutil.copyfile(path, path + ".bak")
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent="\t")
        if os.path.exists(path):
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


API_URL = "https://www.swimtop.pl/api/zawodnik/{}"
USER_AGENT = "Mozilla/5.0 swimtop-script"
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")


class FetchError(Exception):
    pass


def fetch_athlete(slug, *, opener=urllib.request.urlopen, retries=3, sleep=time.sleep):
    req = urllib.request.Request(API_URL.format(quote(slug, safe="-_.~")), headers={"User-Agent": USER_AGENT})
    last_error = None
    for attempt in range(retries):
        if attempt:
            sleep(attempt)
        try:
            with opener(req, timeout=30) as resp:
                body = resp.read()
        except urllib.error.HTTPError as e:
            if e.code < 500:
                raise FetchError(f"HTTP {e.code}") from e
            last_error = f"HTTP {e.code}"
            continue
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_error = str(e)
            continue
        try:
            data = json.loads(body.decode("utf-8"))
        except ValueError as e:
            raise FetchError("odpowiedź nie jest JSON-em") from e
        if not isinstance(data, dict) or not data.get("found"):
            raise FetchError("zawodnik nie został odnaleziony")
        return data
    raise FetchError(f"błąd pobierania po {retries} próbach: {last_error}")


def collect_slugs(args, file):
    raw = list(args)
    if file:
        with open(file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    raw.append(line)
    slugs = []
    for item in raw:
        slug = extract_slug(item)
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs


def main(argv=None, *, fetch=fetch_athlete, sleep=time.sleep):
    parser = argparse.ArgumentParser(description="Pobiera starty zawodników z swimtop.pl do results.json")
    parser.add_argument("inputs", nargs="*", help="URL profilu lub slug zawodnika")
    parser.add_argument("--file", help="plik z listą URL-i/slugów, jeden w wierszu")
    parser.add_argument("--out", default=DEFAULT_OUT, help="plik wynikowy (domyślnie results.json obok skryptu)")
    args = parser.parse_args(argv)
    try:
        slugs = collect_slugs(args.inputs, args.file)
    except OSError as e:
        print(f"Nie można wczytać listy: {e}", file=sys.stderr)
        return 2
    if not slugs:
        parser.error("podaj co najmniej jeden URL/slug lub --file")
    try:
        db = load_db(args.out)
    except DbError as e:
        print(e, file=sys.stderr)
        return 2

    failures, succeeded = [], 0
    for i, slug in enumerate(slugs):
        if i:
            sleep(0.5)
        try:
            api = fetch(slug)
        except FetchError as e:
            failures.append((slug, str(e)))
            continue
        try:
            base_key, athlete, warnings = build_entry(api, now_iso())
            for w in warnings:
                print(f"UWAGA: {w}", file=sys.stderr)
            key, added, skipped = merge_athlete(db, base_key, athlete)
        except Exception as e:
            failures.append((slug, f"nieoczekiwany błąd: {e!r}"))
            continue
        succeeded += 1
        print(f"{key}: dopisano {added}, pominięto duplikatów {skipped}")

    if succeeded:
        try:
            save_db(args.out, db)
        except OSError as e:
            print(f"Nie można zapisać {args.out}: {e}", file=sys.stderr)
            return 2
    if failures:
        print("Niepowodzenia:")
        for slug, reason in failures:
            print(f"  {slug}: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
