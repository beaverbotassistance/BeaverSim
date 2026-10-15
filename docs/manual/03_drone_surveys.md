# 3. Drone surveys: from photos to maps

Most of our imagery comes from small drones: hundreds or thousands of overlapping photos, turned into one
map by software. This chapter explains how that works, how the result is placed on the Earth, and why the
way it was placed decides how far you can trust it. It ends with our own two cases: the Alaska surveys,
placed by RTK, and the 2018 Montana surveys, placed by hand.

## You will learn

- What a drone survey records, and how to read it from a photo's metadata
- How photogrammetry turns photos into an orthomosaic and a surface model
- How fine the result is (ground sample distance), and why
- How the result is positioned: consumer GNSS, RTK, PPK, ground control
- What georeferencing by hand does, and what error it leaves

## 1. A drone survey

A survey drone flies a grid of straight lines at constant height, taking photos with large overlaps: Pix4D
recommends at least **75% frontal and 60% side overlap** in general, and at least 85% both ways over forest
and dense vegetation ([Pix4D, image acquisition plan](https://support.pix4d.com/hc/en-us/articles/202557459)).
Every point of the ground is then seen in many photos, from different angles.

Each photo carries metadata in its **EXIF** block ([CIPA DC-008, the Exif standard](https://www.cipa.jp/std/documents/e/DC-X008-Translation-2019-E.pdf)):
the camera model, the capture time and the GPS position. DJI drones add an **XMP** block with the flight and
gimbal data: height above the take-off point, and the camera's angles (a pitch of −90° means pointing straight
down).

The 2018 Montana surveys used a **DJI Phantom 4 Pro**, camera model `FC6310`: a 1-inch, 20-megapixel sensor,
an 8.8 mm lens with an 84° field of view, photos of 5472 × 3648 pixels, a mechanical shutter, and GPS/GLONASS
positioning ([DJI, Phantom 4 Pro user manual](https://dl.djicdn.com/downloads/phantom_4_pro/20171017/Phantom_4_Pro_Pro_Plus_User_Manual_EN.pdf)).

**In the pipeline**, the photo reader takes camera, time and position from each photo's EXIF, and a folder of
photos becomes one catalogue item whose footprint surrounds the photo positions
([`readers/photos.py`](../../data_acquisition/readers/photos.py), [`stac.photos_item`](../../data_acquisition/catalog/stac.py)).

## 2. Photogrammetry: from photos to maps

**Structure from motion** finds the same features in overlapping photos, works out where each photo was
taken and how the camera was pointing, and from that rebuilds the ground in 3D
([structure from motion](https://en.wikipedia.org/wiki/Structure_from_motion)). From the 3D model the
software produces:

- a **digital surface model** (DSM): the height of every point of the top surface;
- an **orthomosaic**: one image of the ground as seen from straight above, every pixel moved to its true
  position using the DSM ([OpenDroneMap, outputs](https://docs.opendronemap.org/outputs/)).

Common programs are Agisoft [Metashape](https://www.agisoft.com/) (used for Montana), Pix4D (used for the
Alaska surveys) and the open-source [OpenDroneMap](https://docs.opendronemap.org/).

## 3. How fine: ground sample distance

The **ground sample distance** (GSD) is the size of one pixel on the ground. It depends on the flight height
`H`, the camera's focal length `F`, its sensor width `SW` and the image width in pixels `imW`
([Pix4D, GSD](https://support.pix4d.com/hc/en-us/articles/202559809)). By similar triangles, one pixel covers

```
GSD = SW × H / (F × imW)
```

For the Phantom 4 Pro the manual gives `F` = 8.8 mm and `imW` = 5472 px. It does not give the sensor width,
but its field of view does: a diagonal of 84° at 8.8 mm means a sensor diagonal of 2 × 8.8 × tan(42°) =
15.8 mm, which for a 3:2 sensor is 13.2 mm wide. At the 42.8 m above take-off recorded in the Montana photos,
that is 1.17 cm per pixel. The Montana orthomosaic chunks have pixels of about 1.3 by 1.4 cm. Two reasons can
make them larger: the ground under the camera need not be at the height of the take-off point, and the hand
georeferencing (section 5) stretched the pixels slightly differently in x and y.

## 4. Where: positioning

The photos' positions are what place the map on the Earth. How good they are depends on the receiver:

| Positioning | How | Typical accuracy |
|---|---|---|
| **Consumer GNSS** | the drone's own GPS/GLONASS receiver | metres: the Phantom 4 Pro holds its position to ±1.5 m horizontally, ±0.5 m vertically with GPS ([DJI manual](https://dl.djicdn.com/downloads/phantom_4_pro/20171017/Phantom_4_Pro_Pro_Plus_User_Manual_EN.pdf)) |
| **RTK** (real-time kinematic) | corrections from a base station or network during the flight | about 1 cm + 1 ppm horizontally, 1.5 cm + 1 ppm vertically for a Phantom 4 RTK ([DJI, Phantom 4 RTK specs](https://www.dji.com/phantom-4-rtk/info)) |
| **PPK** (post-processed kinematic) | the same corrections, applied after the flight from a base station's log | similar to RTK; no radio link needed during the flight |
| **Ground control points** (GCPs) | marks on the ground surveyed with a precise receiver, found in the photos | as good as the survey of the marks ([OpenDroneMap, GCPs](https://docs.opendronemap.org/gcp/)) |

With consumer GNSS only, each survey is internally consistent, but two surveys of the same place can be
**offset from each other by metres**. Comparing dates then needs **co-registration**: moving one survey onto
another using features both can see.

Heights need care too. DJI records two: the **absolute altitude** (also the EXIF GPS altitude) and the
**relative altitude**, the height above the take-off point. In the Rumney survey of 26 July 2018 the photos'
absolute altitudes span 1243 to 1334 m, while their relative altitudes never exceed 43 m. The take-off altitude
they imply (absolute minus relative) changes from flight to flight, from 1244 to 1291 m: the flights started
from different places, or the drone's estimate of its take-off altitude changed between them. What sets the scale of the photos (section 3) is the camera's distance to the
ground, which the relative altitude approximates only where the ground is at the take-off height.

## 5. Georeferencing by hand

When the positions are not good enough, an image can be moved by hand in GIS software: the person clicks
**control points**, the same feature in the image and on a reference (another survey, a basemap), and the
software fits a transformation through them. ArcGIS calls this georeferencing
([Esri, overview of georeferencing](https://doc.esri.com/en/arcgis-pro/latest/help/data/imagery/overview-of-georeferencing.html)).

A **first-order polynomial** is an **affine** transformation: it can shift, rotate, scale and shear the image,
but keeps straight lines straight. With more control points than the six numbers it needs, it is fitted by
least squares, and each control point is left with a **residual**, the distance between where the fit puts it
and where it was clicked. The residuals measure how well one affine can describe the image's distortions; they
do not measure how good the reference was.

ArcGIS keeps such an adjustment in the image's `.aux.xml` sidecar (as a `GeodataXform`) and, when saved, in a
`.tfwx` world file ([chapter 1](01_geospatial_data.md)). Most other software ignores both, and shows the image
where it was before.

## Case: Alaska by RTK, Montana by hand

**Alaska (2021-2024).** The Seward Peninsula surveys were flown with RTK (a DJI D-RTK 2 base station); the
team's 35 Pix4D processing reports all state that no ground control was used in processing. Their summaries record `positioning: [rtk]`
([`summaries/arcticdata_abon_2024.yaml`](../../data_acquisition/summaries/arcticdata_abon_2024.yaml)).
Surveys of different years can be compared directly.

**Montana (2018-2019).** The Phantom 4 Pro had consumer GNSS only, so every survey was co-registered by hand in
ArcGIS, twice: the full orthomosaic tiles in October 2019 (4 to 18 control points each), and again in January
2020, cut into pieces ("chunks", 4 to 9 control points each). The annotations were drawn on the chunks. What we measured
([chapter 11](11_field_data.md)):

- the fits leave rms residuals of 0.004-2.5 m per image: half under 0.16 m, 96% under 1 m;
- for the same pixels, a tile's and a chunk's georeferencing disagree by 0.1-3 m (in the course's extract:
  0.64 m on 26 July, 0.09 m on 6 August);
- the dam outlines follow the image edges of their chunks to 0.1-0.36 m (median per date), but those of the
  full tiles only to 0.5-1.9 m.

The pipeline reproduces ArcGIS's georeferencing exactly (it writes the same affine into a sidecar GDAL reads),
so annotations and imagery line up as they did for the person who drew them. It cannot make two dates agree
better than the hand co-registration did: that is a job for a later co-registration step, which every
annotation is flagged for (`needs_inspection`).

## Exercises

Notebook: [`notebooks/03_drone_surveys.ipynb`](notebooks/03_drone_surveys.ipynb) (work in a copy); solutions in
[`solutions/notebooks/03_drone_surveys.ipynb`](solutions/notebooks/03_drone_surveys.ipynb).

1. **A photo's metadata.** Read the EXIF of one photo of the Montana extract with
   `data_acquisition.readers.photos.exif`: camera, time, position, altitude. Then find, in the file's XMP block,
   DJI's `RelativeAltitude`, `AbsoluteAltitude` and `GimbalPitchDegree`. What do they tell you? Which of the two
   altitudes is the same as the EXIF one?
2. **Ground sample distance.** Derive the Phantom 4 Pro's sensor width from its field of view and focal length,
   then compute the GSD at the photo's relative altitude. Compare with 1.3 cm.
3. **One photo's footprint.** How many metres of ground does one photo cover at that height, across and along?
   With 75% frontal overlap, how far apart are consecutive photos?
4. **An affine fit.** Make 8 control points from a known affine plus random errors of 0.5 m; fit an affine by
   least squares; print the residuals and their rms. How do they change with 4 points, or 20?
5. **Two georeferencings.** The extract has, for each date, the same area from the chunk and from the full tile,
   on the same grid. Measure the shift between them with `skimage.registration.phase_cross_correlation`, in metres.
6. **Find it in the code.** Which function writes ArcGIS's adjustment into a sidecar, and which one reads the
   control points from an `.aux.xml`?

## Where this lives

- [`data_acquisition/readers/photos.py`](../../data_acquisition/readers/photos.py): EXIF of photos (`exif`, `info`).
- [`data_acquisition/catalog/stac.py`](../../data_acquisition/catalog/stac.py): `photos_item`, the footprint of a survey.
- [`data_acquisition/readers/geotiff.py`](../../data_acquisition/readers/geotiff.py): `arcgis_adjustment`,
  `unapplied_georeference`.
- [`data_acquisition/sources/field.py`](../../data_acquisition/sources/field.py): `georeference` (ArcGIS's fit
  written as a sidecar).
- [`data_acquisition/sources/field_alignment.py`](../../data_acquisition/sources/field_alignment.py): how well
  annotations sit on their images.

## Sources

- CIPA, [Exif 2.32 (DC-008)](https://www.cipa.jp/std/documents/e/DC-X008-Translation-2019-E.pdf)
- DJI, [Phantom 4 Pro user manual](https://dl.djicdn.com/downloads/phantom_4_pro/20171017/Phantom_4_Pro_Pro_Plus_User_Manual_EN.pdf),
  [Phantom 4 RTK specifications](https://www.dji.com/phantom-4-rtk/info)
- Pix4D, [image acquisition plan](https://support.pix4d.com/hc/en-us/articles/202557459),
  [ground sampling distance](https://support.pix4d.com/hc/en-us/articles/202559809)
- OpenDroneMap, [documentation](https://docs.opendronemap.org/), [outputs](https://docs.opendronemap.org/outputs/),
  [ground control points](https://docs.opendronemap.org/gcp/); Agisoft, [Metashape](https://www.agisoft.com/)
- [Structure from motion](https://en.wikipedia.org/wiki/Structure_from_motion)
- Esri, [overview of georeferencing](https://doc.esri.com/en/arcgis-pro/latest/help/data/imagery/overview-of-georeferencing.html)
