"""Finishing downloads: which check a file passes, read-only files, the download log, served MD5 headers."""
import base64
import hashlib
import zipfile
from email.message import Message

import pytest

from data_acquisition.sources import downloads, http


@pytest.fixture
def file(tmp_path):
    path = tmp_path / "data.bin"
    path.write_bytes(b"beaver" * 1000)
    return path


def _serve(monkeypatch, md5=None, size=None):
    monkeypatch.setattr(http, "served", lambda url: (md5, size))


def test_record_checksum_first(file, monkeypatch):
    _serve(monkeypatch)                                   # the server is never needed
    md5 = hashlib.md5(file.read_bytes()).hexdigest()
    assert downloads.verify(file, "u", ("md5", md5)) == "record md5"
    with pytest.raises(IOError):
        downloads.verify(file, "u", ("md5", "0" * 32))


def test_served_md5_when_the_record_cannot_decide(file, monkeypatch):
    md5 = hashlib.md5(file.read_bytes()).hexdigest()
    _serve(monkeypatch, md5=md5)
    assert downloads.verify(file, "u", ("md5", "1" * 32 + "-3")) == f"served md5 (record {'1' * 32}-3 not checkable)"
    assert downloads.verify(file, "u", None) == "served md5"
    _serve(monkeypatch, md5="0" * 32)
    with pytest.raises(IOError):
        downloads.verify(file, "u", None)


def test_size_only_must_be_allowed(tmp_path, monkeypatch):
    path = tmp_path / "pack.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("a.txt", "alpha")
    _serve(monkeypatch, size=path.stat().st_size)
    with pytest.raises(IOError):
        downloads.verify(path, "u", None)
    assert downloads.verify(path, "u", None, size_only=True) == "served size + zip CRC-32 (no md5 published)"


def test_finish_and_log(file, tmp_path, monkeypatch):
    _serve(monkeypatch)
    md5 = hashlib.md5(file.read_bytes()).hexdigest()
    row = downloads.finish(file, tmp_path, "https://x/data.bin", ("md5", md5), source="test",
                           identifier="doi:10.0/x", record={"title": "T", "licence": "CC0-1.0"})
    assert not file.stat().st_mode & 0o222 and row["path"] == "data.bin" and row["verified_by"] == "record md5"
    log = tmp_path / "downloads.csv"
    downloads.log(log, [row])
    downloads.log(log, [dict(row, verified_by="again")])          # same path: replaced, not added
    assert list(downloads.read_log(log).values())[0]["verified_by"] == "again"


def test_stated_md5_headers():
    digest = hashlib.md5(b"x").digest()
    for name, value in (("x-ms-blob-content-md5", base64.b64encode(digest).decode()),
                        ("Content-MD5", base64.b64encode(digest).decode()),
                        ("x-goog-hash", f"crc32c=AAAA, md5={base64.b64encode(digest).decode()}".split(", ")[1]),
                        ("ETag", f'"{digest.hex()}"')):
        headers = Message()
        headers[name] = value
        assert http.stated_md5(headers) == digest.hex(), name
    multipart = Message()
    multipart["ETag"] = f'"{digest.hex()}-2"'
    assert http.stated_md5(multipart) is None                         # a multipart ETag is not an MD5
