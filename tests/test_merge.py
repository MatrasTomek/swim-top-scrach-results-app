import json
import os

import pytest

from helpers import TS
from swimtop import DbError, load_db, merge_athlete, save_db


def start(**kw):
    s = {"zawody": "", "data": "1/1/2026", "miejscowosc": "X", "basen": "25m", "konkurencja_nr": 0,
         "dystans": "50m", "styl": "dowolny", "plec": "", "tor": 0, "czas": "30.00",
         "punkty": 300, "timestamp_pobrania": TS}
    s.update(kw)
    return s


def athlete(starts, year=2012, club="Nowy"):
    return {"imie": "A", "nazwisko": "B", "rok_urodzenia": year, "klub": club, "starty": starts}


def test_new_athlete_added():
    db = {}
    key, added, skipped = merge_athlete(db, "b_a", athlete([start(), start(dystans="100m")]))
    assert (key, added, skipped) == ("b_a", 2, 0)
    assert len(db["b_a"]["starty"]) == 2


def test_second_run_adds_nothing():
    db = {}
    a = athlete([start(), start(dystans="100m")])
    merge_athlete(db, "b_a", a)
    assert merge_athlete(db, "b_a", a) == ("b_a", 0, 2)
    assert len(db["b_a"]["starty"]) == 2


def test_old_format_time_counts_as_duplicate():
    db = {"b_a": athlete([start(czas="00:00:35.80")], year=None)}
    _, added, skipped = merge_athlete(db, "b_a", athlete([start(czas="35.80")]))
    assert (added, skipped) == (0, 1)


def test_duplicates_within_one_response_collapse():
    db = {}
    _, added, skipped = merge_athlete(db, "b_a", athlete([start(), start()]))
    assert (added, skipped) == (1, 1)


def test_old_entries_untouched_including_lap():
    lap = start(styl="dowolny Lap", punkty=None, czas="31.25", data="6/12/2025")
    db = {"b_a": athlete([lap], year=None)}
    merge_athlete(db, "b_a", athlete([start()]))
    assert db["b_a"]["starty"][0] == lap
    assert len(db["b_a"]["starty"]) == 2


def test_club_kept_year_filled_when_null():
    db = {"b_a": athlete([], year=None, club="Stary")}
    merge_athlete(db, "b_a", athlete([start()], year=2012, club="Nowy"))
    assert db["b_a"]["klub"] == "Stary" and db["b_a"]["rok_urodzenia"] == 2012
    db = {"b_a": athlete([], year=2013, club="Stary")}
    merge_athlete(db, "b_a", athlete([start()], year=2013))
    assert db["b_a"]["rok_urodzenia"] == 2013


def test_namesake_gets_year_suffix():
    db = {"b_a": athlete([start()], year=2010)}
    key, added, _ = merge_athlete(db, "b_a", athlete([start()], year=2012))
    assert key == "b_a_2012" and added == 1
    assert len(db["b_a"]["starty"]) == 1


def test_namesake_reuses_suffixed_key():
    db = {"b_a": athlete([start()], year=2010), "b_a_2012": athlete([start()], year=2012)}
    key, added, skipped = merge_athlete(db, "b_a", athlete([start()], year=2012))
    assert (key, added, skipped) == ("b_a_2012", 0, 1)


def test_load_db_missing_returns_empty(tmp_path):
    assert load_db(str(tmp_path / "nope.json")) == {}


@pytest.mark.parametrize("content", ["", "{not json", "[1, 2]"])
def test_load_db_corrupt_raises(tmp_path, content):
    p = tmp_path / "results.json"
    p.write_text(content, encoding="utf-8")
    with pytest.raises(DbError) as e:
        load_db(str(p))
    assert str(p) in str(e.value)


def test_save_db_writes_bak_and_tab_indent(tmp_path):
    p = tmp_path / "results.json"
    p.write_text('{"old": 1}', encoding="utf-8")
    save_db(str(p), {"was_amelia": {"imie": "Wąs"}})
    assert (tmp_path / "results.json.bak").read_text(encoding="utf-8") == '{"old": 1}'
    text = p.read_text(encoding="utf-8")
    assert "\t" in text and "Wąs" in text and "\\u" not in text
    assert json.loads(text) == {"was_amelia": {"imie": "Wąs"}}
    assert [f.name for f in tmp_path.iterdir() if f.name.endswith(".tmp")] == []


def test_save_db_failure_leaves_original(tmp_path, monkeypatch):
    p = tmp_path / "results.json"
    p.write_text('{"old": 1}', encoding="utf-8")

    def boom(*a, **k):
        raise OSError("boom")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        save_db(str(p), {"new": 2})
    assert p.read_text(encoding="utf-8") == '{"old": 1}'
    assert sorted(f.name for f in tmp_path.iterdir()) == ["results.json", "results.json.bak"]


def test_old_entry_without_starty_and_malformed_starts_do_not_crash():
    db = {"b_a": {"imie": "A", "nazwisko": "B"}}
    assert merge_athlete(db, "b_a", athlete([start()])) == ("b_a", 1, 0)
    db = {"b_a": athlete([{"data": "1/1/2026"}, start(czas=None)], year=None)}
    assert merge_athlete(db, "b_a", athlete([start()])) == ("b_a", 1, 0)


def test_save_db_keeps_first_backup_on_repeated_saves(tmp_path):
    p = tmp_path / "results.json"
    p.write_text('{"orig": 1}', encoding="utf-8")
    save_db(str(p), {"v": 1})
    save_db(str(p), {"v": 2})
    assert (tmp_path / "results.json.bak").read_text(encoding="utf-8") == '{"orig": 1}'
    assert json.loads(p.read_text(encoding="utf-8")) == {"v": 2}


def test_save_db_preserves_file_mode(tmp_path):
    p = tmp_path / "results.json"
    p.write_text("{}", encoding="utf-8")
    os.chmod(p, 0o755)
    save_db(str(p), {"v": 1})
    assert os.stat(p).st_mode & 0o777 == 0o755
