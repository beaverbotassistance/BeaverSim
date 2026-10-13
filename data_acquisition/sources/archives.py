#!/usr/bin/env python3
"""Archive extraction for source clients: verified against the archive's own checksums, read-only.

A repository that publishes a zip lists (and checksums) only the zip. This extracts it into a folder
named after the archive (``RCRImages.zip`` -> ``RCRImages/``, or the archive's own top folder), checks
every member against the CRC-32 stored in the zip, and makes the extracted files read-only. Files
already extracted are checked, never overwritten. Summaries then name the archive in each extracted
file's ``archive`` field, so the catalog records where the file came from.

    python -m data_acquisition.sources.archives "<root>/zenodo/<dataset>/RCRImages.zip"
"""
import argparse
import stat
import zipfile
import zlib
from pathlib import Path
from typing import List

CHUNK = 8 * 1024 * 1024


def _crc(path: Path) -> int:
    crc = 0
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            crc = zlib.crc32(block, crc)
    return crc


def _base(archive: Path, z: zipfile.ZipFile) -> Path:
    """Where members extract: the archive's own top folder if it has one, else ``<archive stem>/``."""
    names = [i.filename for i in z.infolist() if not i.is_dir()]
    top = {n.split("/", 1)[0] for n in names}
    return archive.parent if len(top) == 1 and all("/" in n for n in names) else archive.parent / archive.stem


def verify_member(archive: Path, extracted: Path) -> bool:
    """True if ``extracted`` matches the CRC-32 of its member in ``archive``; raises if it is not a member."""
    with zipfile.ZipFile(archive) as z:
        base = _base(archive, z).resolve()
        for info in z.infolist():
            if (base / info.filename).resolve() == extracted.resolve():
                return _crc(extracted) == info.CRC
    raise KeyError(f"{extracted} is not a member of {archive.name}")


def extract(archive: Path) -> List[Path]:
    """Extract ``archive`` next to itself; returns the extracted files. Raises on a CRC mismatch."""
    if not zipfile.is_zipfile(archive):
        raise ValueError(f"{archive.name}: not a zip archive")
    out = []
    with zipfile.ZipFile(archive) as z:
        base = _base(archive, z)
        for info in z.infolist():
            if info.is_dir():
                continue
            target = (base / info.filename).resolve()
            if base.resolve() not in target.parents:
                raise ValueError(f"{archive.name}: member {info.filename} would extract outside {base}")
            if target.exists():
                if _crc(target) != info.CRC:
                    raise IOError(f"{target}: differs from {archive.name}; not overwritten")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                part = target.with_name(target.name + ".part")
                with z.open(info) as src, open(part, "wb") as dst:
                    for block in iter(lambda: src.read(CHUNK), b""):
                        dst.write(block)
                if _crc(part) != info.CRC:
                    raise IOError(f"{info.filename}: CRC mismatch after extraction")
                part.rename(target)
            target.chmod(target.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
            out.append(target)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("archive", type=Path)
    files = extract(parser.parse_args().archive)
    print(f"{len(files)} files extracted or checked, CRC-32 verified")


if __name__ == "__main__":
    main()
