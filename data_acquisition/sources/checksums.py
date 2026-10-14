"""File checksums in the forms repositories publish them.

- plain digests: ``("md5", hex)``, ``("sha256", hex)``, ``("sha1", hex)``;
- S3-style multipart upload ETags: ``("s3etag", "<hex>-<parts>")``, the MD5 of the parts' MD5s. Object
  stores (S3, Google Cloud Storage through its S3 interface) report these for files uploaded in parts.
  A one-part ETag is always checkable; a several-part one only when the part size is known, so common
  part sizes are tried.

:func:`check` returns True or False when the checksum can be decided, and None when it cannot (a
multipart ETag whose part size is none of the common ones). Callers then fall back to another
checksum, e.g. the MD5 the storage states when serving the file.
"""
import hashlib
import math
import re
from pathlib import Path
from typing import Optional, Tuple

CHUNK = 8 * 1024 * 1024
MIB, MB = 1024 * 1024, 1000 * 1000
# part sizes of common upload tools (AWS CLI and SDKs, gsutil, rclone, MinIO, iRODS), smallest first
PART_SIZES = sorted({k * MIB for k in (5, 8, 10, 15, 16, 25, 32, 50, 64, 100, 128, 256, 512, 1024)}
                    | {k * MB for k in (5, 8, 10, 16, 50, 64, 100, 128, 256, 512, 1000)})
ETAG = re.compile(r"^([0-9a-f]{32})-(\d+)$", re.I)


def parse(algorithm: str, value: str) -> Tuple[str, str]:
    """Normalise a published checksum: a ``<hex>-<n>`` value is an S3 multipart ETag, whatever it is called."""
    value = value.strip().strip('"').lower()
    if ETAG.match(value):
        return "s3etag", value
    return algorithm.lower().replace("-", ""), value


def digest(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _etag(path: Path, part: int) -> str:
    digests = []
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(part), b""):
            digests.append(hashlib.md5(block).digest())
    return f"{hashlib.md5(b''.join(digests)).hexdigest()}-{len(digests)}"


def check(path: Path, algorithm: str, value: str) -> Optional[bool]:
    """Does ``path`` match the published checksum? None when it cannot be decided."""
    algorithm, value = parse(algorithm, value)
    if algorithm != "s3etag":
        return digest(path, algorithm) == value
    parts = int(ETAG.match(value).group(2))
    size = path.stat().st_size
    if parts == 1:
        return f"{hashlib.md5(bytes.fromhex(digest(path, 'md5'))).hexdigest()}-1" == value
    for part in PART_SIZES:
        if math.ceil(size / part) == parts and _etag(path, part) == value:
            return True
    return None     # no common part size reproduces it: undecided, not wrong
