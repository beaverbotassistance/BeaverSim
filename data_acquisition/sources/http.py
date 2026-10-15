"""HTTP for the source clients: retries, resumable downloads, and the MD5 a server states for a file.

Standard library only (``urllib``). Every request is retried after a growing wait on rate limits,
server errors and dropped connections; anything else (e.g. 404) is raised at once.
"""
import base64
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

CHUNK = 8 * 1024 * 1024
WAITS = (10, 30, 60, 120, 300)            # seconds before each retry of a temporary error
TEMPORARY = (429, 500, 502, 503, 504)


def retry(action: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """``action(*args, **kwargs)``, retried after a growing wait on temporary errors."""
    for wait in (*WAITS, None):
        try:
            return action(*args, **kwargs)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if wait is None or (isinstance(e, urllib.error.HTTPError) and e.code not in TEMPORARY):
                raise
            print(f"  {e}; retrying in {wait} s")
            time.sleep(wait)
    raise AssertionError("unreachable")       # the last attempt either returns or raises


def _get(url: str, timeout: int) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def get(url: str, timeout: int = 120) -> bytes:
    """The body of ``url`` (retried)."""
    return retry(_get, url, timeout)


def https(url: str) -> str:
    """``url`` with ``http://`` upgraded to ``https://`` (some records list plain-http links)."""
    return re.sub(r"^http://", "https://", url)


def _fetch(url: str, dest: Path, size: Optional[int]) -> None:
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(url)
    if have:
        request.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(request, timeout=300) as r, open(part, "ab" if have and r.status == 206 else "wb") as f:
        for block in iter(lambda: r.read(CHUNK), b""):
            f.write(block)
    if size is not None and part.stat().st_size != size:
        raise ConnectionError(f"{dest.name}: got {part.stat().st_size} bytes, expected {size}")
    part.rename(dest)


def fetch(url: str, dest: Path, size: Optional[int] = None, retries: bool = True) -> None:
    """Stream ``url`` to ``dest`` through a ``.part`` file, resuming one left by an earlier attempt when the
    server supports ranges; checks the size when it is known. ``retries=False`` raises at the first error."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    (retry if retries else lambda action, *args: action(*args))(_fetch, url, dest, size)


def stated_md5(headers) -> Optional[str]:
    """The whole file's MD5 as the server states it in ``headers``, or None: Azure ``x-ms-blob-content-md5``,
    Google ``x-goog-hash: md5=``, ``Content-MD5``, or a plain (non-multipart) ETag. These describe the stored
    object, also in the answer to a byte-range request."""
    for name in ("x-ms-blob-content-md5", "Content-MD5"):
        if headers.get(name):
            return base64.b64decode(headers[name]).hex()
    for value in headers.get_all("x-goog-hash") or []:
        if value.strip().lower().startswith("md5="):
            return base64.b64decode(value.split("=", 1)[1].strip()).hex()
    etag = (headers.get("ETag") or "").strip('"').lower()
    return etag if re.fullmatch(r"[0-9a-f]{32}", etag) else None


def _served(url: str) -> Tuple[Optional[str], Optional[int]]:
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=120) as r:
        md5, length = stated_md5(r.headers), r.headers.get("Content-Length")
    if md5 is None:     # some stores state the MD5 only when content is requested: ask for one byte
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=0-0"}), timeout=120) as r:
            md5 = stated_md5(r.headers)
            total = (r.headers.get("Content-Range") or "").rsplit("/", 1)[-1]
            length = length or (total if total.isdigit() else None)
    return md5, int(length) if length else None


def served(url: str) -> Tuple[Optional[str], Optional[int]]:
    """(MD5, size) the server states for the file at ``url``, each None when it states none (retried)."""
    return retry(_served, url)
