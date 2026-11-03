# 0. Setup: environment, drives, sample data

Before the first exercise you need the code, a Python environment with its libraries, the GDAL
command-line tools, and the course's sample data. This chapter sets them up and checks that they work.
Everything here has been tested on a fresh environment built from the repository's requirement files.

## You will learn

- How to install the Python environment and the GDAL tools the pipeline uses
- Which data roots exist, where they live, and which ones the course needs
- How to make the sample data root, and how the notebooks find it
- How to check the whole setup with the tests

## 1. The repository

The code is in a private GitHub repository; you need to be added to it. Clone it with SSH and enter it:

```
git clone git@github.com:beaverbotassistance/BeaverSim.git
cd BeaverSim
```

Some large files of the simulator are stored with [Git LFS](https://git-lfs.com/) (`git lfs install`, then
`git lfs pull`). The dataset pipeline and this course do not need them.

The parts you will use most:

```
data_acquisition/      the dataset pipeline (chapter 7 gives the tour)
docs/manual/           this course: chapters, notebooks/, solutions/, data/, tools/
docs/dataset/          the pipeline's design and reference documents
tests/dataset/         the pipeline's tests
output/                everything generated locally (never committed)
```

## 2. The Python environment

The pipeline is tested with Python 3.12. You create a
[virtual environment](https://docs.python.org/3/library/venv.html) in the repository folder and install the
libraries into it. The steps depend on where you work, so first check:

```
ls -d /opt/dua-venv
```

**If it prints `/opt/dua-venv`, you are in the lab's sandbox**: follow the sandbox steps. If it says `No such file or
directory` (your own computer, or a lab computer outside the sandbox), follow the standard steps.

Standard:

```
python3 -m venv beaversim_venv
source beaversim_venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

Lab sandbox:

```
python3 -m venv beaversim_venv
source beaversim_venv/bin/activate
unset PYTHONPATH                                        # for this terminal, until the patch below is in place
pip install -r requirements.txt -r requirements-dev.txt
python docs/manual/tools/patch_sandbox_venv.py          # once: makes the environment ignore PYTHONPATH
source beaversim_venv/bin/activate
```

**Why the sandbox differs.** Its terminals start with `PYTHONPATH` pointing to `/opt/dua-venv` and the system
packages, and Python searches `PYTHONPATH` before the active environment
([Python docs](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONPATH)). Those packages would replace the
environment's own: `pip` stops working (`cannot import name 'cli'`), and libraries silently have other versions.
[`patch_sandbox_venv.py`](tools/patch_sandbox_venv.py) makes `activate` clear `PYTHONPATH`, `deactivate` put it back,
and Jupyter notebooks start without it, so your other sandbox projects are not affected. It does nothing outside
the sandbox. If you ever recreate the environment, run the sandbox steps again.

To check the result anywhere (the first line should be empty in the sandbox, and the path should be inside your
`beaversim_venv`):

```
echo "$PYTHONPATH"
python -c "import pandas; print(pandas.__version__, pandas.__file__)"
```

[`requirements.txt`](../../requirements.txt) pins every library with its exact version (the geospatial
ones are rasterio, pyogrio, geopandas, pyproj, shapely and pystac); [`requirements-dev.txt`](../../requirements-dev.txt)
adds the tools to test and check the code (pytest, ruff). Always activate the environment before running
anything: commands below assume it.

**If ROS is installed on your own machine**, outside the sandbox, it adds its own Python packages to the
`PYTHONPATH` of every terminal, and some of them break pytest. The repository's
[`pytest.ini`](../../pytest.ini) already disables the ROS pytest plugins; if imports still fail, run
`python docs/manual/tools/patch_sandbox_venv.py --force` once: it protects the environment in the same way.

## 3. The GDAL command-line tools

[GDAL](https://gdal.org/en/stable/) is the library that reads almost every geospatial format. The Python
libraries carry their own copy of it, but the field step ([chapter 11](11_field_data.md)) also needs its
command-line tools, `ogr2ogr` and `ogrinfo`. On Ubuntu they come with the `gdal-bin` package
([other systems](https://gdal.org/en/stable/download.html)):

```
sudo apt install gdal-bin
ogr2ogr --version
```

Note that your machine now has **two** GDAL installations, the system one and the one inside rasterio, often
of different versions, each with its own copy of PROJ. Chapter 2 shows why that matters.

## 4. Claude Code

Dataset summaries are drafted by Claude in a [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
session, then reviewed by a person ([chapter 9](09_describing_a_dataset.md)). A Claude Pro or Max subscription
covers it; the pipeline does not use the paid API.

## 5. Data roots

The pipeline works on **data roots**, folders that hold datasets. Two exist today, both on the field-season
drive (an external disk, mounted on Linux at `/media/<user>/Seagate Portable Drive`):

| Data root | Holds | Made by |
|---|---|---|
| `open_datasets/` | open datasets downloaded from repositories, and their catalogues in `stac/` | the source clients ([chapter 8](08_open_datasets.md)) |
| `beaver_dataset/` | the field seasons 2018-2019, reorganised from the original folders, and their catalogues | the field step ([chapter 11](11_field_data.md)) |

The original folders of the field seasons (`2018 Field Season/`, `2019 Field Season/`) are **never written to**.
The drive is formatted NTFS; if it is unplugged without unmounting, Linux may mount it read-only until it is
repaired ([appendix B](B_troubleshooting.md)).

**The course does not need the drive.** It uses:

- the **sample data root**, generated in a second (next section);
- the **Montana extract**, a 4 MB piece of Rumney Ranch committed with the course
  ([`docs/manual/data/montana_extract/`](data/montana_extract/README.md));
- one small open dataset that you download in chapter 8.

## 6. The sample data root

[`docs/manual/tools/make_sample.py`](tools/make_sample.py) writes a small dataset folder that looks like a
repository download: an invented site, "Training Pond", with an orthomosaic, a DSM, an elevation grid without a
CRS, a dam layer, six drone photos and a metadata record. It also writes the sample's own **site registry**.

```
python docs/manual/tools/make_sample.py --out output/manual/sample_root
export BEAVER_SITES=output/manual/sample_root/sites.yaml
```

The pipeline normally reads the registry of real sites, [`data_acquisition/sites.yaml`](../../data_acquisition/sites.yaml).
The environment variable `BEAVER_SITES` points it to another file for as long as the terminal is open, so the
course never touches the real registry ([`summary.load_sites`](../../data_acquisition/catalog/summary.py)).

The notebooks do all this themselves: their first cell finds the repository, makes the sample data root if
it is missing, and sets `BEAVER_SITES`.

## 7. Notebooks

Each chapter's exercises are in a notebook under [`docs/manual/notebooks/`](notebooks/), with the solutions
under [`docs/manual/solutions/notebooks/`](solutions/notebooks/). Open them in VS Code or
[Jupyter](https://jupyter.org/) with the `beaversim_venv` kernel. **Work in a copy**: the notebooks are
regenerated by [`docs/manual/tools/build_notebooks.py`](tools/build_notebooks.py), which overwrites them.

## 8. Check the setup

```
python -m pytest tests/dataset -q
```

All tests should pass in a few seconds. They build small catalogues from synthetic data, run the course's
reference summary and every solution notebook; if they pass, your environment can do everything the course asks.

## Exercises

Notebook: [`notebooks/00_setup.ipynb`](notebooks/00_setup.ipynb) (work in a copy); solutions in
[`solutions/notebooks/00_setup.ipynb`](solutions/notebooks/00_setup.ipynb).

1. Make the sample data root and list its files with their sizes. Which file is the largest, and why?
2. Print the versions of GDAL and PROJ inside rasterio, of PROJ inside pyproj, and of the system's `ogr2ogr`.
   How many different versions of PROJ do you have?
3. Read [`pytest.ini`](../../pytest.ini): which plugins are disabled, and why?
4. Print the path of the site registry the pipeline uses, with and without `BEAVER_SITES`.

## Where this lives

- [`requirements.txt`](../../requirements.txt), [`requirements-dev.txt`](../../requirements-dev.txt): the libraries.
- [`pytest.ini`](../../pytest.ini): test settings.
- [`docs/manual/tools/make_sample.py`](tools/make_sample.py): the sample data root.
- [`data_acquisition/catalog/summary.py`](../../data_acquisition/catalog/summary.py) (`load_sites`): which registry is read.
- [`tests/dataset/test_manual.py`](../../tests/dataset/test_manual.py): the tests that keep the course working.

## Sources

- Python, [venv](https://docs.python.org/3/library/venv.html); [Git LFS](https://git-lfs.com/); [Jupyter](https://jupyter.org/)
- GDAL, [documentation](https://gdal.org/en/stable/), [download](https://gdal.org/en/stable/download.html)
- Anthropic, [Claude Code overview](https://docs.claude.com/en/docs/claude-code/overview)
