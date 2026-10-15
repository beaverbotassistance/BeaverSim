# Montana extract (Rumney Ranch, 2018)

A 60 m × 60 m piece of Rumney Ranch, Montana, around one beaver dam, at two survey dates:
26 July and 6 August 2018. It is used by the course's exercises on field data, coordinates and
georeferencing. Made by [`docs/manual/tools/make_montana_extract.py`](../../tools/make_montana_extract.py)
from `beaver_dataset/sites/rumney_ranch/` on the field-season drive; `extract.json` lists the exact source
of every file.

> **Internal data.** These are unpublished field data of a site whose land status and data governance are
> still being settled (see [chapter 5](../../05_data_governance.md)). The repository is private for this
> reason. Do not copy these files outside it.

## Contents

```
<date>/
  orthomosaic_chunk.tif       the chunk the annotations were drawn on, with its ArcGIS georeferencing applied
  orthomosaic_full_tile.tif   the same area from the full tile, with its own (earlier) georeferencing
  annotations/<layer>.gpkg    every annotation layer of that date, clipped to the box
  photos/DJI_*.JPG            three photos taken over the box
extract.json                  the box, the source of every file, and the alignment rows of the clipped outlines
```

## What was changed from the originals

- **Orthomosaics:** cut to the box and resampled from about 1.3 cm to 5 cm per pixel (average of the
  pixels), RGB only (the alpha band dropped), JPEG-compressed. Their CRS and georeferencing are those of
  `beaver_dataset`: the ArcGIS adjustment applied, and the ARC System zone written on a sphere
  ([field naming](../../../dataset/field_naming.md)).
- **Annotations:** the features of each layer that touch the box, unchanged (geometry, Z and M, attributes),
  with a `source_fid` column giving the feature's id in `beaver_dataset`, which corrections refer to.
- **Photos:** downscaled to 800 pixels on the longest side; EXIF (camera, time, GPS) kept.
