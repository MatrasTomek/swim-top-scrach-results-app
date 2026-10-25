from helpers import TS, load, minimal_api, perf
from swimtop import build_entry, now_iso

FIELDS = {"zawody", "data", "miejscowosc", "basen", "konkurencja_nr", "dystans",
          "styl", "plec", "tor", "czas", "punkty", "timestamp_pobrania"}


def test_amelia_entry():
    api = load("amelia-was-2012")
    key, a, warns = build_entry(api, TS)
    assert key == "was_amelia"
    assert (a["imie"], a["nazwisko"], a["rok_urodzenia"]) == ("Amelia", "Wąs", 2012)
    assert len(a["starty"]) == len(api["performances"])
    first = a["starty"][0]
    assert set(first) == FIELDS
    assert first["konkurencja_nr"] == 0 and first["tor"] == 0
    assert first["plec"] == "Kobiet"
    assert first["timestamp_pobrania"] == TS


def test_known_first_start():
    _, a, _ = build_entry(load("amelia-was-2012"), TS)
    first = a["starty"][0]
    assert first["dystans"] == "400m" and first["styl"] == "zmienny"
    assert first["basen"] == "50m" and first["czas"] == "5:21.33" and first["punkty"] == 552
    assert first["data"] == "10/7/2026"
    assert first["zawody"] == "Letnie Mistrzostwa Polski Juniorow Młodszych 14 Lat W Pływaniu"
    assert first["miejscowosc"] == "OLSZTYN"


def test_split_start_gets_lap_suffix_and_null_points():
    api = minimal_api(perf(isSplit=True, event="50 m st. dowolnym", points=None, time="31.25"))
    _, a, _ = build_entry(api, TS)
    assert a["starty"][0]["styl"] == "dowolny Lap"
    assert a["starty"][0]["punkty"] is None


def test_unknown_event_is_skipped_with_warning():
    api = minimal_api(perf(event="4x50 m st. dowolnym"))
    _, a, warns = build_entry(api, TS)
    assert a["starty"] == [] and len(warns) == 1
    assert "4x50 m st. dowolnym" in warns[0]


def test_missing_optional_fields():
    api = {"found": True, "user": {"firstName": "A", "lastName": "B", "birthYear": None}, "performances": []}
    key, a, _ = build_entry(api, TS)
    assert key == "b_a"
    assert a["rok_urodzenia"] is None and a["starty"] == [] and a["klub"] == ""


def test_missing_meet_gives_empty_zawody():
    p = perf()
    del p["meet"]
    _, a, _ = build_entry(minimal_api(p), TS)
    assert a["starty"][0]["zawody"] == ""


def test_gender_mapping():
    _, a, _ = build_entry(minimal_api(perf(), gender="Mężczyzna"), TS)
    assert a["starty"][0]["plec"] == "Mężczyzn"
    _, a, _ = build_entry(minimal_api(perf(), gender="Inne"), TS)
    assert a["starty"][0]["plec"] == ""
    _, a, _ = build_entry(minimal_api(perf(), gender=None), TS)
    assert a["starty"][0]["plec"] == ""


def test_now_iso_format():
    import re
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", now_iso())


def test_performance_missing_date_or_time_is_skipped_with_warning():
    api = minimal_api(perf(date=None), perf(time=None), perf(), "to nie jest słownik")
    _, a, warns = build_entry(api, TS)
    assert len(a["starty"]) == 1 and len(warns) == 3
