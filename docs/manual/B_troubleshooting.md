# B. Troubleshooting

Problems met while building the pipeline and the course, with their cause and fix. Each links to the chapter that
explains it.

## Environment

**pytest fails at start with `PluginValidationError: Plugin 'launch_testing'`.**
ROS adds its Python packages to `PYTHONPATH`, and some of them register pytest plugins that this pytest rejects.
Run pytest from the repository root, so [`pytest.ini`](../../pytest.ini) switches them off. For a test file outside
the repository, pass the settings explicitly: `python -m pytest -c pytest.ini --rootdir . <file>`
([chapter 18](18_testing.md)). If imports still fail, `env -u PYTHONPATH python -m pytest ...`.

**`ogr2ogr: command not found`** (the field step).
The GDAL command-line tools are a system package: `sudo apt install gdal-bin` on Ubuntu, which needs
administrator rights; on a lab machine, ask its administrator ([chapter 0](00_setup.md)).

**Plots do not appear in a notebook after importing `field_alignment`.**
The module switches matplotlib to a file-only backend when imported. Run `%matplotlib inline` after the import
(finding 24).

**ruff reports hundreds of `UP006` findings.**
The repository has no ruff configuration, so ruff's defaults apply. Use the rules the code follows:
`ruff check --select E,F,W --line-length 120 <files>` (finding 25, [chapter 18](18_testing.md)).

## Data and files

**A file in the repository holds three lines starting `version https://git-lfs.github.com/spec/v1`.**
It is a [Git LFS](https://git-lfs.com/) pointer: every `.csv` in the repository is stored with LFS
([`.gitattributes`](../../.gitattributes)), among them [`docs/dataset/missing_photos.csv`](../dataset/missing_photos.csv).
Install LFS and fetch the files: `git lfs install`, then `git lfs pull`.

**`Permission denied` when changing or deleting a downloaded file.**
Downloaded, extracted and linked files are read-only on purpose ([chapter 8](08_open_datasets.md)). If you really must
remove one (a failed download, a scratch copy), make it writable first: `chmod u+w <file>`. Never do this to the
originals of the field drive.

**A download stops with "differs from the repository's md5", and the next run fails the same way.**
The bad file stays where the good one belongs (finding 9). Delete it (`chmod u+w`, then `rm`) and run the client
again.

**A file is "missing" from the build report, but it is on disk.**
Paths in a summary are relative to the group's `folder`, and the folder is relative to the data root given with
`--root`. Check both, and the exact spelling (case, spaces) ([chapter 9](09_describing_a_dataset.md)).

**An item folder is on disk but not in the catalogue.**
A rebuild does not delete folders of items that no longer exist (finding 13). Follow the catalogue's links, as pystac
does; do not scan the folder ([chapter 10](10_building_and_curating.md)).

## The field-season drive

**The drive mounts read-only, or does not mount ("volume is dirty").**
It is formatted NTFS. If it was unplugged without unmounting, or Windows was not shut down cleanly, the volume is
marked dirty, and Linux's [ntfs3 driver](https://docs.kernel.org/filesystems/ntfs3.html) will not mount it for writing.
The safe repair is Windows' `chkdsk /f` on the drive. On Linux,
[`ntfsfix -d`](https://manpages.ubuntu.com/manpages/noble/man8/ntfsfix.8.html) clears the flag and fixes basic
inconsistencies only; use it only if no Windows machine is at hand. Always unmount before unplugging
(`udisksctl unmount -b /dev/sdX2`, or the file manager's eject).

**`os.link` fails with "Invalid cross-device link"** (the field step).
Hard links work only within one filesystem: `beaver_dataset/` must be on the same drive as the original folders
([chapter 17](17_field_step_internals.md)).

**A field step build deleted a file I had put in the site folder.**
`prune` removes every file the plan does not make (finding 23). Keep your own files outside
`beaver_dataset/sites/`.

## Coordinates

**The same layer lands about 30 km away in one tool and not in another.**
Its CRS is an ESRI ARC System zone (Equidistant Cylindrical), which ArcGIS evaluates on a sphere and PROJ 9.8 or
newer on the ellipsoid ([chapter 2](02_coordinates.md)). The field step writes the sphere explicitly into every
exported layer; data exported by other means may still carry the ambiguous form.

**A raster lands in the wrong place, or nowhere, in QGIS but has an `.aux.xml` from ArcGIS.**
ArcGIS stores its georeferencing as an adjustment that GDAL does not apply (`unapplied_georeference`,
[chapter 3](03_drone_surveys.md)). In `beaver_dataset`, the field step has written the adjustment as the file's own
georeferencing; in other datasets the flag says so.

**Three PROJ versions on one machine.**
pyproj, rasterio and the system's GDAL tools each carry their own PROJ (on this machine 9.5.1, 9.8.1 and 9.4.0).
That is normal; check positions with more than one when a CRS is unusual ([chapter 2](02_coordinates.md)).
