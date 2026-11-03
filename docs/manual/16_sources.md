# 16. Sources: downloads and checksums

[Chapter 8](08_open_datasets.md) used the source clients. This chapter opens them: the contract every client
follows, the shared code that downloads, verifies and logs a file, and the forms of checksum repositories publish.
It is what you need to read or write a client for a new repository ([chapter 19](19_extending.md)).

## You will learn

- The contract of a source client, mapped onto the model client
- How a download resumes, retries and is verified
- The checksum forms (plain digests, multipart ETags, served MD5s) and when each can be decided
- How dataset folders are named

## 1. The contract

A client is code for one repository **standard** (a protocol and a record format), never for one dataset. Every
client in [`data_acquisition/sources/`](../../data_acquisition/sources/) follows the same contract, which the intake
prompt also gives Claude ([`intake.py`](../../data_acquisition/intake.py)):

1. the same core options: `--root`, `--id` (repeatable), `--filter` (a regular expression on file names), `--list`
   (some clients add their own: DataONE's `--repository` and `--summary`, CKAN's `--api` and `--no-md5-ok`);
2. `--list` prints the title, licence, files and sizes, and downloads nothing;
3. the record is saved **unchanged**, next to the files, under the name `RECORDS` gives its format
   ([chapter 13](13_readers.md));
4. files go into `dataset_folder(root, <repository>, <identifier>)`;
5. each file is downloaded with `http.fetch` and finished with `downloads.finish`: verified, made read-only, logged;
6. a file already on disk is not downloaded again, only verified again; nothing downloaded is ever deleted or
   overwritten;
7. archives are extracted only with `archives.extract` (CRC-checked, read-only, never overwriting), after the archive
   itself is verified;
8. what is specific to one dataset goes into its summary, never into the client.

[`zenodo.py`](../../data_acquisition/sources/zenodo.py) is the model: 67 lines, every point above in plain view. The
others add what their standard needs: DataONE resolves a DOI to a package and its members; HydroShare saves two
responses in one file; CKAN skips resources that are web pages, and allows size-only checks with `--no-md5-ok`.

## 2. Downloading: `http.py`

Standard library only ([`urllib.request`](https://docs.python.org/3/library/urllib.request.html)):

- **retries** (`http.retry`): rate limits (429), server errors (500, 502, 503, 504) and dropped connections are
  retried after 10, 30, 60, 120 and 300 s; anything else (a 404) fails at once;
- **resume** (`http.fetch`): the file is written to `<name>.part`; a later attempt asks for the rest with an HTTP
  [`Range`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests) header, and appends only if the
  server answers 206 (partial content); otherwise it starts again;
- **size**: when the record states a size, a `.part` of another size is not renamed;
- **served MD5** (`http.served`, `http.stated_md5`): many storage services state a file's MD5 in a header:
  `Content-MD5`, Azure's `x-ms-blob-content-md5`, Google's `x-goog-hash: md5=`, or a plain 32-hex `ETag`. A `HEAD`
  request is tried first, then a one-byte range request, since some services state it only when serving content.
  (Google's combined header, `crc32c=…,md5=…`, is not read yet: finding 22 in
  [`course_findings.md`](../dataset/course_findings.md).)

## 3. Verifying: `downloads.py` and `checksums.py`

`downloads.verify` tries, in order:

1. the **record's checksum**, if it can be decided (`checksums.check`): a plain digest (MD5, SHA-1, SHA-256), or an
   S3 **multipart ETag**;
2. else the **MD5 the server states**;
3. else, only where the client allows it (`size_only`, CKAN's `--no-md5-ok`), the **size** the server states and,
   for a zip, the CRC-32 of every member.

A file that passes none is refused. The log row's `verified_by` says which check it passed.

**Multipart ETags.** Object stores that receive a file in parts report an ETag of the form `<hex>-<parts>`: the MD5
of the concatenated MD5s of the parts, not of the file
([AWS: checking object integrity](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html)).
It can be recomputed only with the part size the uploader used, which is not published.
`checksums.check` tries the part sizes of common upload tools (5 MiB to 1 GiB, and their decimal
counterparts); if none reproduces it, the answer is **None, undecided**, not False, and the next check is tried.

`downloads.finish` then makes the file read-only and returns its row for `downloads.csv` (`downloads.log` merges
rows by path): source, DOI, file, path, size, an MD5 computed on arrival, licence, title, date, link, `verified_by`.

## 4. Dataset folders

`dataset_folder(root, repository, identifier)`
([`sources/__init__.py`](../../data_acquisition/sources/__init__.py)) names a dataset's folder from **the exact
version downloaded**: `doi_<doi>` for a DOI (in any of its spellings: `doi:10.x/y`, `10.x/y`, a doi.org link), and
`id_<identifier>` for anything else, so a folder name never claims a DOI the dataset does not have. Characters
other than letters, digits, `.`, `_` and `-` become `_`. For Zenodo, a concept DOI (all versions) resolves to the
latest version, whose DOI names the folder.

## 5. Trying it without the network

Exercises 6 to 10 run against a **fake repository**: a small web server the notebook starts on your own machine, which
serves records and files from a dictionary. The clients do not know the difference, so you can follow a whole download
offline. The clients' addresses (`zenodo.RECORD`, `pangaea.FILES`, ...) are module constants, which is what makes this
possible; `http.https` is replaced for those runs, because the server speaks plain HTTP.

| Module | Functions | What to remember |
|---|---|---|
| `http` | `get`, `https`, `served`, `retry` | temporary errors wait and try again; a 404 fails at once |
| `checksums` | `parse`, `digest`, `check` | `parse` recognises an ETag by its form, whatever the record calls it |
| `downloads` | `verify`, `finish`, `read_only`, `listing`, `log`, `read_log` | one log row per path: downloading again replaces it |
| `archives` | `extract`, `verify_member` | extracting again only checks; a changed file is refused, never overwritten |
| clients | `record_of`, `download`; HydroShare's `list_files`, CKAN's `package_id` | same contract, different ways of speaking to the repository |
| [`intake.py`](../../data_acquisition/intake.py) | `write_prompt` | it tells Claude to stop and wait for approval before downloading |

## Exercises

These run offline: they use local files (`file://` links), headers built by hand, and a fake repository (section 5).

Notebook: [`notebooks/16_sources.ipynb`](notebooks/16_sources.ipynb) (work in a copy); solutions in
[`solutions/notebooks/16_sources.ipynb`](solutions/notebooks/16_sources.ipynb).

1. **The contract in the model client.** Print `zenodo.py` and find, for each point of the contract, the line that
   does it.
2. **Folders.** Name the folders of `10.5281/zenodo.1`, `https://doi.org/10.18739/A2CZ3253W`, `hs:abc123` and a CKAN
   package id.
3. **Checksums.** For a file of 12 MiB: compute its MD5 and SHA-256; make its multipart ETag with 5 MiB parts and
   check it; check an ETag made with 7 MiB parts. Why is the answer None and not False?
4. **Served MD5s.** Build response headers with `Content-MD5`, with `x-goog-hash`, and with a multipart `ETag`; what
   does `http.stated_md5` return for each?
5. **Download, resume, finish.** Leave a stale `.part` of the file in a scratch root, fetch it from its `file://`
   link, finish it against its MD5, log it, and read the log row. Then finish a copy against a wrong MD5: what
   happens to the file (finding 9 in [`course_findings.md`](../dataset/course_findings.md))?

6. **The HTTP helpers.** `web.get`, `web.served` with and without a stated MD5, `web.https`; `web.retry` on a function that
   fails twice; `web.get` on a page that does not exist.
7. **Verifying and logging.** `checksums.parse`; `downloads.verify` four ways; `read_only`; `listing`, with a filter and
   with checks; the same path logged twice, read with `read_log`.
8. **Archives.** `archives.extract` and `verify_member`, again, and after changing a file; a file that is not a member,
   and one that is not a zip.
9. **Five clients, one contract.** `record_of` and `download` for Zenodo, DataONE, HydroShare, PANGAEA and CKAN against the
   fake repository. What is the same, and what does each add?
10. **Intake.** `intake.write_prompt` for one link and for two records. Where does it tell Claude to stop?

## Where this lives

- [`data_acquisition/sources/http.py`](../../data_acquisition/sources/http.py): `retry`, `get`, `fetch`, `served`, `stated_md5`.
- [`data_acquisition/sources/downloads.py`](../../data_acquisition/sources/downloads.py): `verify`, `finish`, `listing`, `log`, `read_log`.
- [`data_acquisition/sources/checksums.py`](../../data_acquisition/sources/checksums.py): `parse`, `digest`, `check`, `PART_SIZES`.
- [`data_acquisition/sources/archives.py`](../../data_acquisition/sources/archives.py): extraction with CRC-32.
- [`data_acquisition/sources/__init__.py`](../../data_acquisition/sources/__init__.py): `dataset_folder`.
- [`tests/dataset/test_downloads.py`](../../tests/dataset/test_downloads.py),
  [`test_checksums_archives.py`](../../tests/dataset/test_checksums_archives.py): their tests.

## Sources

- Python, [`urllib.request`](https://docs.python.org/3/library/urllib.request.html), [`hashlib`](https://docs.python.org/3/library/hashlib.html)
- MDN, [HTTP range requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests),
  [ETag](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag)
- AWS, [checking object integrity](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html)
  (multipart checksums); Google Cloud, [hashes and ETags](https://cloud.google.com/storage/docs/hashes-etags)
- DOI, [the DOI handbook](https://www.doi.org/the-identifier/resources/handbook/)
