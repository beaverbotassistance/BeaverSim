"""The builder end to end on the synthetic data root, and the curate checks on its items."""
import pystac

from data_acquisition.catalog import build, descriptors, stac
from data_acquisition.steps.curate import curate_item

FOLDER = "repo/doi_10.0000_test"


def _build(root, summary):
    s = dict(summary, sites={"test_site": {"name": "Test site", "crs": "EPSG:32603", "colonies": None,
                                           "land_status": None, "governance": None}},
             _path=str(root / "test_dataset.yaml"))
    catalog, report = build.build(root, s)
    return {i.id: i for i in catalog.get_items(recursive=True)}, report, catalog, s


def test_items_and_ids(root, summary):
    items, report, _, _ = _build(root, summary)
    assert sorted(items) == sorted([
        "test_site_2021-08-03_orthomosaic", "test_site_2021-08-03_dsm", "test_site_2018-08-14_dtm",
        "test_site_2010_annotations", "test_site_2013_annotations", "test_site_2021-08-03_survey_points_gcp",
        "test_site_1990-01-01_2025-05-05_model_output", "test_site_2021-08-03_orthomosaic_inner"])
    assert report == {"missing": [], "undescribed": [], "unsupported": [], "unattached": [], "unmatched_layers": []}


def test_reports_and_undescribed_files(root, summary):
    (root / FOLDER / "stray.dat").write_text("not in the summary")
    items, report, _, _ = _build(root, summary)
    assert report["undescribed"] == [f"{FOLDER}/stray.dat"]          # the .ovr sidecar is not reported
    assert "report" in items["test_site_2021-08-03_orthomosaic"].assets
    assert "report" in items["test_site_2021-08-03_dsm"].assets
    assert "archive" in items["test_site_2021-08-03_orthomosaic"].assets


def test_bands_crs_and_tables(root, summary):
    items, _, _, _ = _build(root, summary)
    dsm = items["test_site_2021-08-03_dsm"]
    assert [b["name"] for b in dsm.assets["dsm"].extra_fields["eo:bands"]] == ["elevation", "uncertainty"]
    dtm = items["test_site_2018-08-14_dtm"]
    assert dtm.properties["beaver:crs_from_summary"] == "EPSG:32603"
    assert any(q["flag"] == "crs_from_summary" for q in dtm.properties["beaver:quality"])
    table = items["test_site_1990-01-01_2025-05-05_model_output"]
    assert table.geometry is None and table.properties["beaver:fields"] == {"id": "ReachID", "value": "oCC_EX"}
    flags = {q["flag"] for q in table.properties["beaver:quality"]}
    assert {"non_spatial", "date_unknown"} <= flags


def test_layers_become_items(root, summary):
    items, _, _, _ = _build(root, summary)
    layer = items["test_site_2013_annotations"]
    assert layer.properties["beaver:layer"] == "dams_2013"
    assert layer.properties["beaver:layers"][0]["features"] == 3
    assert layer.common_metadata.start_datetime.year == 2013


def test_archive_provenance(root, summary):
    items, _, _, _ = _build(root, summary)
    provenance = descriptors.get_field(items["test_site_2021-08-03_orthomosaic_inner"], "provenance")
    assert provenance["archive"] == f"{FOLDER}/bundle.zip"


def test_descriptors_come_from_the_reviewer(root, summary):
    items, _, _, _ = _build(root, summary)
    origin = items["test_site_2021-08-03_orthomosaic"].properties["beaver:origin"]["site"]
    assert origin == {"source": "manual", "by": "Tester", "date": "2026-10-14"}


def test_curate_checks(root, summary):
    items, _, _, s = _build(root, summary)
    for item in items.values():
        curate_item(item, s)
    ortho = items["test_site_2021-08-03_orthomosaic"]
    assert descriptors.get_field(ortho, "season") == "summer"
    assert {q["flag"] for q in ortho.properties["beaver:quality"]} >= {"nodata_undeclared"}
    assert descriptors.get_field(items["test_site_1990-01-01_2025-05-05_model_output"], "season") == "unknown"
    assert set(descriptors.missing(ortho)) == {"colonies", "land_status", "governance", "licence", "positioning"}


def test_catalog_saves_and_validates(root, summary, tmp_path):
    _, _, catalog, _ = _build(root, summary)
    path = stac.save(catalog, tmp_path / "stac")
    reloaded = pystac.Catalog.from_file(str(path))
    assert len(list(reloaded.get_items(recursive=True))) == 8


def test_season():
    import datetime
    assert descriptors.season(datetime.date(2021, 8, 3), 65.0) == "summer"
    assert descriptors.season(datetime.date(2021, 8, 3), -40.0) == "winter"
    assert descriptors.season(datetime.date(2022, 3, 27), 65.0) == "spring"


def test_inspect_becomes_a_quality_flag(root, summary):
    file = next(f for f in summary["groups"][0]["files"]
                if f.get("product") == "orthomosaic" and not f.get("variant"))
    file["inspect"] = "outlines may be offset from the imagery"
    items, _, _, _ = _build(root, summary)
    flags = descriptors.get_field(items["test_site_2021-08-03_orthomosaic"], "quality")
    assert {"flag": "needs_inspection", "detail": "outlines may be offset from the imagery", "source": "manual"} in flags
