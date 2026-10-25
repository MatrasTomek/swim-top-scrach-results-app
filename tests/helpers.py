import json
import pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
TS = "2026-10-25T10:00:00.000Z"


def load(slug):
    return json.loads((FIXTURES / f"{slug}.json").read_text(encoding="utf-8"))


def perf(**kw):
    p = {
        "event": "50 m st. dowolnym", "pool": "25m", "time": "30.00", "points": 300,
        "date": "2026-01-02", "city": "OLSZTYN", "isSplit": False,
        "meet": {"title": "Zawody testowe"},
    }
    p.update(kw)
    return p


def minimal_api(*performances, first="Jan", last="Kowalski", year="2012", gender="Mężczyzna", club="Klub"):
    return {
        "found": True,
        "user": {"firstName": first, "lastName": last, "birthYear": year, "gender": gender, "club": club},
        "performances": list(performances),
    }
