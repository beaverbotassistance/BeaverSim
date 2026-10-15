# Drone surveys: from photos to maps

> Status: outline. Learning goals, sections and exercises; the text is still to be written.

## You will learn

- Know how photogrammetry turns photos into an orthomosaic and a DSM
- Understand positioning: consumer GNSS, RTK, PPK, ground control
- Explain georeferencing and co-registration, and their errors

## Sections

1. A drone survey: flight plan, overlap, camera, EXIF
2. Photogrammetry: structure from motion, orthomosaic, DSM/DTM (Metashape, Pix4D, OpenDroneMap)
3. Positioning: GNSS, RTK and PPK, ground control and check points
4. Georeferencing by hand: control points and an affine fit; residuals
5. Co-registration between dates
6. Case: Montana 2018 (consumer GPS, tiles and chunks georeferenced in ArcGIS) vs Alaska (RTK)

## Exercises

1. Read the EXIF of a sample photo (camera, time, position).
2. Compute an affine fit from control points and its residuals.
3. Compare the two georeferencings of a Rumney chunk and its full tile.

## Where this lives

- [`data_acquisition/readers/photos.py`](../../data_acquisition/readers/photos.py)
- [`data_acquisition/readers/geotiff.py`](../../data_acquisition/readers/geotiff.py)
- [`data_acquisition/sources/field.py`](../../data_acquisition/sources/field.py)

## Sources

- (links to the sources of each concept, checked when the chapter is written)
