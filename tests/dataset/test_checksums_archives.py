"""Checksums (plain digests, S3 multipart ETags) and archive extraction."""
import hashlib
import zipfile

import pytest

from data_acquisition.sources import archives, checksums

MIB = 1024 * 1024


def _etag(data: bytes, part: int) -> str:
    digests = [hashlib.md5(data[i:i + part]).digest() for i in range(0, len(data), part)]
    return f"{hashlib.md5(b''.join(digests)).hexdigest()}-{len(digests)}"


@pytest.fixture
def data_file(tmp_path):
    path = tmp_path / "data.bin"
    path.write_bytes(bytes(range(256)) * (6 * MIB // 256))           # 6 MiB: two 5 MiB parts
    return path


def test_parse():
    assert checksums.parse("md5", "8BDB5CDA50A0B2DBA9B3277980FFCC64-2") == ("s3etag", "8bdb5cda50a0b2dba9b3277980ffcc64-2")
    assert checksums.parse("MD5", "b4014bc52faeeb5afe703646d7ca0d08") == ("md5", "b4014bc52faeeb5afe703646d7ca0d08")


def test_plain_digests(data_file):
    data = data_file.read_bytes()
    assert checksums.check(data_file, "md5", hashlib.md5(data).hexdigest()) is True
    assert checksums.check(data_file, "sha256", hashlib.sha256(data).hexdigest()) is True
    assert checksums.check(data_file, "md5", "0" * 32) is False


def test_etags(data_file):
    data = data_file.read_bytes()
    assert checksums.check(data_file, "md5", _etag(data, len(data))) is True        # one part: always checkable
    assert checksums.check(data_file, "md5", _etag(data, 5 * MIB)) is True          # a common part size
    assert checksums.check(data_file, "md5", _etag(data, 3 * MIB + 7)) is None      # unknown part size: undecided
    assert checksums.check(data_file, "md5", "0" * 32 + "-1") is False


@pytest.fixture
def archive(tmp_path):
    path = tmp_path / "pack.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("pack/a.txt", "alpha")
        z.writestr("pack/sub/b.txt", "beta")
    return path


def test_extract_and_verify(archive):
    files = archives.extract(archive)
    assert sorted(f.name for f in files) == ["a.txt", "b.txt"]
    target = archive.parent / "pack" / "a.txt"
    assert target.read_text() == "alpha" and not target.stat().st_mode & 0o222        # read-only
    assert archives.verify_member(archive, target) is True
    assert len(archives.extract(archive)) == 2                                         # re-run checks, no error


def test_extract_never_overwrites(archive):
    archives.extract(archive)
    target = archive.parent / "pack" / "a.txt"
    target.chmod(0o644)
    target.write_text("changed")
    with pytest.raises(IOError):
        archives.extract(archive)


def test_extract_refuses_paths_outside(tmp_path):
    path = tmp_path / "evil.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("../outside.txt", "x")
        z.writestr("inside.txt", "y")
    with pytest.raises(ValueError):
        archives.extract(path)
