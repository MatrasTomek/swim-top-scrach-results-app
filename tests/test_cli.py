import json
import urllib.error

import pytest

from helpers import load
from swimtop import FetchError, collect_slugs, fetch_athlete, main


class FakeResp:
    def __init__(self, body):
        self.body = body if isinstance(body, bytes) else body.encode("utf-8")

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code):
    return urllib.error.HTTPError("http://x", code, "err", {}, None)


def scripted_opener(*outcomes):
    calls = []

    def opener(req, timeout=None):
        calls.append(req)
        out = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
        if isinstance(out, Exception):
            raise out
        return FakeResp(out)

    opener.calls = calls
    return opener


def no_sleep(_):
    pass


def test_collect_slugs_dedups_and_skips_comments(tmp_path):
    f = tmp_path / "lista.txt"
    f.write_text("# komentarz\n\nhttps://www.swimtop.pl/zawodnik/a-b-2010?x=1\n"
                 "https://swimtop.pl/zawodnik/a-b-2010/\nc-d-2011\n", encoding="utf-8")
    assert collect_slugs([], str(f)) == ["a-b-2010", "c-d-2011"]


def test_collect_slugs_order_is_first_occurrence(tmp_path):
    f = tmp_path / "lista.txt"
    f.write_text("a-b-2010\nc-d-2011\n", encoding="utf-8")
    assert collect_slugs(["https://www.swimtop.pl/zawodnik/c-d-2011", "x-y-2000"], str(f)) == \
        ["c-d-2011", "x-y-2000", "a-b-2010"]


def test_fetch_retries_on_5xx_then_succeeds():
    opener = scripted_opener(http_error(503), http_error(503), json.dumps({"found": True}))
    assert fetch_athlete("a-b-2010", opener=opener, sleep=no_sleep) == {"found": True}
    assert len(opener.calls) == 3
    assert opener.calls[0].full_url.endswith("/api/zawodnik/a-b-2010")
    assert opener.calls[0].get_header("User-agent")


def test_fetch_gives_up_after_retries_on_network_error():
    opener = scripted_opener(urllib.error.URLError("down"))
    with pytest.raises(FetchError):
        fetch_athlete("a-b-2010", opener=opener, sleep=no_sleep)
    assert len(opener.calls) == 3


def test_fetch_404_no_retry_raises():
    opener = scripted_opener(http_error(404))
    with pytest.raises(FetchError):
        fetch_athlete("a-b-2010", opener=opener, sleep=no_sleep)
    assert len(opener.calls) == 1


def test_fetch_html_body_raises_fetcherror():
    with pytest.raises(FetchError):
        fetch_athlete("a-b-2010", opener=scripted_opener("<html>błąd</html>"), sleep=no_sleep)


def test_fetch_found_false_raises():
    with pytest.raises(FetchError):
        fetch_athlete("a-b-2010", opener=scripted_opener(json.dumps({"found": False})), sleep=no_sleep)


def fixture_fetch(slug):
    if slug == "zly-slug-1900":
        raise FetchError("Zawodnik nie został odnaleziony")
    return load(slug)


def run(tmp_path, *args):
    out = tmp_path / "results.json"
    code = main([*args, "--out", str(out)], fetch=fixture_fetch, sleep=no_sleep)
    return code, out


def test_main_merges_two_athletes_and_returns_0(tmp_path):
    code, out = run(tmp_path, "amelia-was-2012", "https://www.swimtop.pl/zawodnik/franciszek-was-2014")
    assert code == 0
    db = json.loads(out.read_text(encoding="utf-8"))
    assert set(db) == {"was_amelia", "was_franciszek"}
    # fixture Amelii zawiera dwa identyczne wpisy (ten sam turniej, dzień, czas) - łączą się w jeden start
    assert len(db["was_amelia"]["starty"]) == len(load("amelia-was-2012")["performances"]) - 1


def test_main_continues_after_failure_and_returns_nonzero(tmp_path, capsys):
    code, out = run(tmp_path, "zly-slug-1900", "amelia-was-2012")
    assert code != 0
    assert "was_amelia" in json.loads(out.read_text(encoding="utf-8"))
    assert "zly-slug-1900" in capsys.readouterr().out


def test_main_corrupt_db_exits_nonzero_without_writing(tmp_path, capsys):
    out = tmp_path / "results.json"
    out.write_text("{zepsute", encoding="utf-8")
    code = main(["amelia-was-2012", "--out", str(out)], fetch=fixture_fetch, sleep=no_sleep)
    assert code != 0
    assert out.read_text(encoding="utf-8") == "{zepsute"
    assert not (tmp_path / "results.json.bak").exists()
    assert "results.json" in capsys.readouterr().err


def test_main_summary_lists_added_and_skipped(tmp_path, capsys):
    run(tmp_path, "amelia-was-2012")
    capsys.readouterr()
    code, _ = run(tmp_path, "amelia-was-2012")
    out = capsys.readouterr().out
    assert code == 0
    assert "was_amelia" in out and "dopisano 0" in out


def test_main_all_failed_does_not_write_file(tmp_path):
    code, out = run(tmp_path, "zly-slug-1900")
    assert code != 0 and not out.exists()


def test_fetch_quotes_non_ascii_slug():
    opener = scripted_opener(json.dumps({"found": True}))
    fetch_athlete("wąs-amelia-2012", opener=opener, sleep=no_sleep)
    assert opener.calls[0].full_url.endswith("/api/zawodnik/w%C4%85s-amelia-2012")


def test_main_unexpected_error_for_one_athlete_does_not_lose_others(tmp_path, capsys):
    def fetch(slug):
        if slug == "popsuty-1":
            return {"found": True, "user": "nie-slownik", "performances": []}
        return load(slug)

    out = tmp_path / "results.json"
    code = main(["amelia-was-2012", "popsuty-1", "--out", str(out)], fetch=fetch, sleep=no_sleep)
    assert code != 0
    assert "was_amelia" in json.loads(out.read_text(encoding="utf-8"))
    assert "popsuty-1" in capsys.readouterr().out
