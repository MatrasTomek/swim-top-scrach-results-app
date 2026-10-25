import pytest

from helpers import load
from swimtop import athlete_key, extract_slug, format_date, normalize_time, parse_event


@pytest.mark.parametrize("text", [
    "https://www.swimtop.pl/zawodnik/amelia-was-2012",
    "https://swimtop.pl/zawodnik/amelia-was-2012/",
    "https://www.swimtop.pl/zawodnik/amelia-was-2012?tab=meets",
    "amelia-was-2012",
    "  amelia-was-2012  ",
])
def test_extract_slug_variants(text):
    assert extract_slug(text) == "amelia-was-2012"


def test_parse_event():
    assert parse_event("400 m st. zmiennym") == ("400m", "zmienny")
    assert parse_event("50 m st. motylkowym") == ("50m", "motylkowy")
    assert parse_event("100 m st. klasycznym") == ("100m", "klasyczny")
    assert parse_event("4x50 m st. dowolnym") is None


@pytest.mark.parametrize("slug", ["amelia-was-2012", "franciszek-was-2014"])
def test_all_fixture_events_parse(slug):
    for p in load(slug)["performances"]:
        assert parse_event(p["event"]) is not None, p["event"]


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
