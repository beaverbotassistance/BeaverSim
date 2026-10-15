# 8. Bringing in an open dataset

The first stage of the pipeline gets data from a repository onto a data root: listed before anything is
downloaded, verified on arrival, logged, and never changed afterwards. This chapter downloads a real dataset,
the beaver dams of the northern Baldwin Peninsula in Alaska (55 KB), extracts its archive, and catalogues it
with its existing summary. It ends with what to do when a dataset comes from a repository the pipeline does not
know yet.

## You will learn

- How to list a dataset's files and licence before downloading
- What the pipeline checks and records when it downloads a file
- How archives are extracted and verified
- How to bring in a dataset from a new repository with Claude

## 1. Source clients

There is one client per kind of repository, in [`data_acquisition/sources/`](../../data_acquisition/sources/):
`dataone` (the Arctic Data Center and other DataONE members), `pangaea`, `zenodo`, `hydroshare` and `ckan`
(government portals). They share the same options:

```
python -m data_acquisition.sources.<repository> --root <data root> --id <doi or id> [--list] [--filter <regex>]
```

- `--list` prints the dataset's title, licence and files with their sizes, and downloads nothing. **Always list
  first**: some datasets are tens of gigabytes, and `--filter` (a regular expression on file names) downloads
  only part of them.
- Without `--list`, the client downloads the files and the dataset's metadata record into
  `<root>/<repository>/<dataset folder>/`. The folder is `doi_<doi>` for a real DOI (`/` written as `_`), or
  `id_<repository id>` for a dataset without one ([`sources.dataset_folder`](../../data_acquisition/sources/__init__.py)).

## 2. What happens on download

For each file ([`sources/http.py`](../../data_acquisition/sources/http.py),
[`sources/downloads.py`](../../data_acquisition/sources/downloads.py)):

1. it is downloaded to a `.part` file, so an interrupted download resumes instead of restarting; when complete
   (and of the size the record states, if it states one) it is renamed to its final name;
2. it is **verified** against the checksum the repository publishes, in whatever form it uses
   ([chapter 4](04_catalogs_and_metadata.md)); if the record has none, against the MD5 the server states while
   serving it. A file that fails stops the download with an error; it is left where it is, not read-only and not
   logged, and **you must delete it** before downloading again (a later run would otherwise keep re-checking it);
3. it is made **read-only**, so nothing later can change it by accident;
4. it gets a row in `<root>/downloads.csv`: the source, the dataset, the file, its size, an MD5 computed on
   arrival, the licence, the date, the URL, and what it was verified against (`verified_by`).

A file already there is not downloaded again, only verified again. The metadata record is saved unchanged, next
to the data.

## 3. Archives

When a repository publishes a zip, its record lists, and checksums, only the zip. The archive tool extracts it:

```
python -m data_acquisition.sources.archives <path to the zip>
```

Every extracted file is checked against the CRC-32 the zip stores for it, made read-only, and never overwritten:
running the tool again only checks ([`sources/archives.py`](../../data_acquisition/sources/archives.py)). The
summary then lists the zip with `role: archive` and gives each extracted file `archive: <the zip>`, so the
catalogue records where it came from and `curate --verify` can check it against the zip.

## 4. A new repository: intake with Claude

A dataset from a repository without a client goes through **intake**
([`data_acquisition/intake.py`](../../data_acquisition/intake.py)):

```
python -m data_acquisition.intake --url <DOI or link> --root <data root> --dataset <slug>
```

writes a prompt for a Claude Code session. The prompt lists the clients and readers that exist, the contract a
new client must follow (the options above, verification, the log, the record saved unchanged, the folder
naming), and the steps: identify the repository; write the client if needed (following
[`sources/zenodo.py`](../../data_acquisition/sources/zenodo.py) as the model); **list and stop for the user's
approval** before downloading; download; then draft the summary ([chapter 9](09_describing_a_dataset.md)). A
client is code for one repository *standard*, used by every dataset from that repository: Claude may write one,
and it is reviewed like any code. What is specific to one dataset still goes only into its summary.

## Case: the Baldwin Peninsula dams, from DOI to catalogue

`doi:10.18739/A2CZ3253W` on the Arctic Data Center: beaver dams mapped on satellite imagery in 2010, 2013 and
2019. Listed, it is one zip of 55 KB under CC BY 4.0. Downloaded, the zip is verified against the record's
SHA-1; extracted, it gives a File Geodatabase with one point layer per year. Its summary already exists
([`summaries/arcticdata_baldwin_dams.yaml`](../../data_acquisition/summaries/arcticdata_baldwin_dams.yaml)), and
works on any data root that holds the same files: built on your own root, it gives one item per year, each
verified against the zip's CRC-32.

## Exercises

These exercises download from the Arctic Data Center (an internet connection is needed). They use their own data
root, `output/manual/open_root`, and the **real** site registry, because the Baldwin Peninsula is a real site.

Notebook: [`notebooks/08_open_datasets.ipynb`](notebooks/08_open_datasets.ipynb) (work in a copy); solutions in
[`solutions/notebooks/08_open_datasets.ipynb`](solutions/notebooks/08_open_datasets.ipynb).

1. **List.** List `doi:10.18739/A2CZ3253W` with the DataONE client. What is its licence, and how large is it?
2. **Download.** Download it into `output/manual/open_root`. Find its row in `downloads.csv` and explain each
   column. Run the download again: what happens?
3. **Extract.** Extract the zip. Which files appeared, and with which permissions? Run the extraction again.
4. **Catalogue.** Check, build and curate it with `--verify`, using the summary `arcticdata_baldwin_dams`. What
   was each item verified against?
5. **Intake.** Write an intake prompt for any Zenodo DOI into `output/manual/intake_example` (nothing is
   downloaded). Read the client contract in it: which rules does it set?
6. **Find it in the code.** Which function downloads a file with resume, and which writes the row of
   `downloads.csv`?

## Where this lives

- [`data_acquisition/sources/`](../../data_acquisition/sources/): `dataone.py`, `pangaea.py`, `zenodo.py`,
  `hydroshare.py`, `ckan.py`; the shared `http.py`, `downloads.py`, `checksums.py`, `archives.py`;
  `__init__.py` (`dataset_folder`).
- [`data_acquisition/intake.py`](../../data_acquisition/intake.py): the intake prompt.
- [`data_acquisition/readers/`](../../data_acquisition/readers/): the record readers each client's record goes to.

## Sources

- [Arctic Data Center](https://arcticdata.io/), [DataONE](https://www.dataone.org/), [Zenodo API](https://developers.zenodo.org/),
  [PANGAEA](https://www.pangaea.de/), [HydroShare](https://www.hydroshare.org/), [CKAN API](https://docs.ckan.org/en/latest/api/index.html)
- The dataset: B. Jones, K. Tape et al., *Northwestern Arctic Alaska beaver dam locations, northern Baldwin
  Peninsula region, 2010-2019*, NSF Arctic Data Center, [doi:10.18739/A2CZ3253W](https://doi.org/10.18739/A2CZ3253W),
  CC BY 4.0
