"""Summary schema: time fields, layer dates, and the checks that reject malformed summaries."""
import copy
import datetime

import pytest

from data_acquisition.catalog import summary as summaries

D = datetime.date


@pytest.mark.parametrize("fields, expected", [
    ({"date": D(2018, 9, 25)}, (D(2018, 9, 25), D(2018, 9, 25), "2018-09-25")),
    ({"date": 2017, "date_precision": "year"}, (D(2017, 1, 1), D(2017, 12, 31), "2017")),
    ({"date": D(2017, 12, 3), "date_precision": "month"}, (D(2017, 12, 1), D(2017, 12, 31), "2017-12")),
    ({"date": D(2024, 2, 1), "date_precision": "month"}, (D(2024, 2, 1), D(2024, 2, 29), "2024-02")),
    ({"start_date": D(2017, 9, 7), "end_date": D(2018, 9, 25)},
     (D(2017, 9, 7), D(2018, 9, 25), "2017-09-07_2018-09-25")),
    ({"date_precision": "unknown", "start_date": D(1990, 1, 1), "end_date": D(2025, 5, 5)},
     (D(1990, 1, 1), D(2025, 5, 5), "1990-01-01_2025-05-05")),
])
def test_epoch(fields, expected):
    assert summaries.epoch(fields) == expected


@pytest.mark.parametrize("fields", [
    {"date": "x"},
    {"start_date": D(2018, 1, 1), "end_date": D(2017, 1, 1)},
    {"date": D(2017, 1, 1), "date_precision": "week"},
    {"date_precision": "unknown", "end_date": D(2025, 5, 5)},          # limits must both be given
])
def test_epoch_rejects(fields):
    with pytest.raises(ValueError):
        summaries.epoch(fields)


@pytest.mark.parametrize("name, spec, expected", [
    ("Kotz_beaver_dams_2012", {"pattern": r"_(\d{4})$"}, {"date": D(2012, 1, 1), "date_precision": "year"}),
    ("dams_2019-07", {"pattern": r"_(\d{4}-\d{2})$", "date_precision": "month"},
     {"date": D(2019, 7, 1), "date_precision": "month"}),
    ("x_20190708", {"pattern": r"_(\d{8})$", "date_precision": "day"}, {"date": D(2019, 7, 8), "date_precision": "day"}),
    ("TestPolygonsMapped", {"pattern": r"_(\d{4})$"}, None),
    ("x_20191308", {"pattern": r"_(\d{8})$", "date_precision": "day"}, None),          # month 13
])
def test_layer_epoch(name, spec, expected):
    assert summaries.layer_epoch(name, spec) == expected


def test_resolve_adds_up_notes():
    merged = summaries.resolve({"site": "a", "notes": ["group"]}, {"path": "f", "notes": ["file"]})
    assert merged["site"] == "a" and merged["notes"] == ["group", "file"]


def test_valid_summary_has_no_problems(summary):
    assert summaries.check(summary, summaries.load_sites()) == []


def _problems(summary, change):
    s = copy.deepcopy(summary)
    change(s)
    return summaries.check(s, summaries.load_sites())


def _file(s, path):
    return next(f for f in s["groups"][0]["files"] if f["path"] == path)


@pytest.mark.parametrize("change, expected", [
    (lambda s: _file(s, "ortho_2021.tif").update(role="report"), "exactly one of product or role"),
    (lambda s: _file(s, "ortho_2021.tif").update(product="ortho"), "product must be one of"),
    (lambda s: _file(s, "dsm_2021.tif").update(product="orthomosaic"), "give each a variant"),
    (lambda s: _file(s, "gcps.csv")["table"].pop("y"), "x and y together"),
    (lambda s: _file(s, "dams.gpkg").update(layers={"pattern": "no_group"}), "regex with one group"),
    (lambda s: _file(s, "reaches.csv").update(fields={"key": "ReachID"}), "fields must be"),
    (lambda s: _file(s, "dem_2018.txt").update(crs="32612"), "crs must be EPSG"),
    (lambda s: s["groups"][0].update(site="nowhere"), "not in data_acquisition/sites.yaml"),
    (lambda s: s.update(sites={"test_site": {"crs": "EPSG:32603"}}), "only hints belong in a summary"),
    (lambda s: s.update(reviewed=True), "reviewed needs by and date"),
    (lambda s: s["groups"][0].update(colour="red"), "unknown field colour"),
])
def test_check_rejects(summary, change, expected):
    assert any(expected in p for p in _problems(summary, change))


def test_anchors_are_rejected():
    assert summaries.anchors("a: &x\n  b: 1\nc: *x\n")
    assert not summaries.anchors("note: 5 * 3 & more\nurl: http://x/*y\n")


def test_registry_checks():
    bad = {"x": {"name": "X", "crs": "32612", "land_status": "private", "level": "country", "contains": ["y"]}}
    problems = " ".join(summaries.check_sites(bad))
    for expected in ("crs must be EPSG", "land_status must be null", "level must be one of", "contains unknown"):
        assert expected in problems


def test_author():
    s = {"authored": {"by": "claude", "model": "m", "date": "d"}, "reviewed": None}
    assert summaries.author(s)[0] == "claude"
    s["reviewed"] = {"by": "Federico Oliva", "date": "d"}
    assert summaries.author(s) == ("manual", {"by": "Federico Oliva", "date": "d"})


def test_inspect_must_be_a_sentence(summary):
    summary["groups"][0]["files"][0]["inspect"] = True
    assert any("inspect must be a sentence" in p for p in summaries.check(summary, summaries.load_sites()))


def test_registry_from_the_environment(tmp_path, monkeypatch):
    other = tmp_path / "other_sites.yaml"
    other.write_text("schema: 1\nsites:\n  elsewhere: {name: Elsewhere, crs: 'EPSG:32612', colonies: null, "
                     "land_status: null, governance: null}\n")
    monkeypatch.setenv("BEAVER_SITES", str(other))
    assert list(summaries.load_sites()) == ["elsewhere"]
