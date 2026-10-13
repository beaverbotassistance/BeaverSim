# Open Beaver Datasets: Checklist

Compiled 12 October 2026, extended 13 October 2026. Purpose: replace the Rumney Ranch
(Blackfeet) data in BeaverSim and Oriel's thesis with openly licensed sources, and find data
that extends our own (longer time series, more sites, elevation).

For each dataset, check: (1) licence, (2) actual files and resolution, (3) land status and any
Indigenous data governance notes, (4) fit for BeaverSim (RGB pipeline, DEM pipeline, or
network/time-series).

Legend for fit: **RGB** = cm-scale imagery for trails and vegetation; **DEM** = terrain for
hydrology; **NET** = dam/pond inventories over time for SEN / graph dynamics.

Verification status: **[x] Checked** means licence and contents were read from the repository
record on 13 October 2026. Unchecked entries are as originally compiled.

---

## Summary

| Need | Best option | Why |
|---|---|---|
| cm-scale imagery **over several years, same sites** | **A2: Seward Peninsula repeat drone surveys (Alaska, 2021–2024)** | 6 beaver sites flown 3–5 times over 4 years; orthomosaic + DSM + multispectral |
| cm-scale imagery, many sites, best quality | **A1: ABON 2024** | CC0, 9 sites, RTK, 5 cm RGB + DSM + multispectral; single date |
| Dam network growth over decades | **B1 + B1c: Kotzebue / Baldwin–Seward dam inventories (2001–2024)** | CC BY 4.0; dam establishment and abandonment |
| Open aerial imagery at 8–30 cm, repeated, anywhere in a country | **C: national orthophoto programmes** (Netherlands, Switzerland, US NAIP) | Clean open licences, regular re-flights |
| Bare-earth elevation | **D: national lidar** | ~1 m DEMs, open in several countries |
| Scouting sites and dates | **E1: Google Earth Pro** | Historical imagery slider; not usable as a data source (see terms) |

Things none of the open sources give: **weekly** surveys within one season (our 2018 data
remains unique for that), and hand-annotated canals and trails per colony.

---

## A. Centimetre-scale drone imagery (RGB / DEM)

### A1. ABON: Arctic Beaver Observation Network, August 2024
- [x] Checked
- **What:** RGB orthomosaics (5 cm GSD), digital surface models (10 cm) and multispectral
  composites (green, red, red edge, NIR; 10 cm) at 9 beaver sites across Arctic Alaska
  (Seward and Baldwin Peninsulas), flown 2–8 August 2024.
- **Acquisition:** DJI Mavic 3 Multispectral, 120 m above ground, 80/70 % overlap, **RTK**
  (DJI D-RTK 2 base) plus GNSS ground control (Leica Viva); processed in Pix4D; WGS84
  UTM zone 3N, ellipsoid heights. Elevation over water is flagged as unreliable.
- **Files:** 30 GeoTIFFs (one RGB, one DSM, one multispectral per site), **24.5 GB** total.
  Sites include Glacier Creek, Grouse Creek, Kotzebue 3, Kotzebue B East and others.
- **Authors:** Benjamin Jones, Kenneth Tape.
- **Repository:** NSF Arctic Data Center, **doi:10.18739/A22R3NZ98**.
- **Licence:** **CC0 1.0** (public domain dedication).
- **Fit:** RGB, DEM. 5 cm resolves ~30 cm trails; NIR enables real NDVI. Single date, but several
  sites overlap with the A2 time series.
- **Watch out:** Land status not stated in the metadata (possible Alaska Native corporation lands).
- **Links:** https://arcticdata.io/catalog/view/doi:10.18739/A22R3NZ98 · https://par.nsf.gov/biblio/10629125

### A2. Seward Peninsula and Baldwin Peninsula repeat drone surveys (Alaska, 2021–2024)
- [x] Checked (dataset list and dates; licence per record still to confirm)
- **What:** The same team (Jones, Tape et al.) flew the same beaver dam and pond sites several
  times over four years: orthomosaic + DSM, and separate multispectral orthomosaics. Together
  with A1 this is a **multi-year, cm-scale time series of beaver-engineered sites**.
- **Sites and dates** (Arctic Data Center records; O = orthomosaic + DSM, M = multispectral):

  | Site | Aug 2021 | Mar 2022 | Aug 2022 | Mar 2023 | Aug 2023 | Spring 2024 | Aug 2024 (ABON) |
  |---|---|---|---|---|---|---|---|
  | Swan Lake drained lake basin (MP64) | O, M | O | O, M | | M | | ? |
  | Swan Lake Creek | | O | O, M | | M | | ? |
  | Upper Nome River (MP31) | O, M | O | O, M | | M | | ? |
  | Glacier Creek Road | O, M | | M | | M | | O, M |
  | Willow Creek (Alaska, not our Montana site) | O | O | O | | | | ? |
  | South Fork Serpentine River | | O | O, M | O | | | ? |
  | Ptarmigan Creek (failed dam) | | | O | | | | |
  | Kotzebue B East / B West / B South / 3 | | | | | O | O (Apr 2024, northern Baldwin) | O, M (B East, 3) |

  "?" = may be one of the ABON 2024 sites; check the ABON file list.
- **Selected DOIs:** Swan Lake MP64 Aug 2021 10.18739/A2J09W600; Upper Nome MP31 Aug 2021
  10.18739/A21Z41V3Q; Glacier Creek Aug 2021 10.18739/A29882P6F; Willow Creek Aug 2021
  10.18739/A2KS6J62X; South Fork Serpentine Mar 2022 10.18739/A22V2CC0N; Swan Lake Creek
  Aug 2022 10.18739/A2C824G5F; Kotzebue B East Aug 2023 10.18739/A20Z70Z6X; northern Baldwin
  spring 2024 10.18739/A29C6S30W. Full list: search "beaver" on arcticdata.io.
- **Licence:** Arctic Data Center publishes under CC0 or CC BY 4.0; confirm on each record.
- **Fit:** RGB, DEM, and multi-year change at the same sites. March flights show snow-covered
  terrain (different use: snow, ice, winter water). Pairs with B1c (dam establishment).
- **Related summary record:** Swan Lake Creek study reach, beaver dams, flowlines and UAS
  imagery 2006–2021, doi:10.18739/A2PK0732F
  (https://par.nsf.gov/biblio/10473921-swan-lake-creek-study-reach-datasets-beaver-dams-flowlines-uas-imagery-seward-peninsula-alaska).
- **Associated paper:** Jones, Tape, Clark, Bondurant, Ward Jones, Gaglioti, Elder, Witharana,
  Miller (Remote Sensing).

### A3. River Tale, Clyst William Cross, Devon, UK (2017, 2018)
- [x] Checked
- **What:** Drone nadir (60 m) and oblique (55 m, ~20°) imagery, mean GSD ~16 mm; SfM point
  clouds, DSM, DTM, canopy height models, DEMs of difference; 40 GCPs. 10 ha willow woodland,
  beavers released 2016. Surveys 7 Sept 2017 and 25 Sept 2018.
- **Title:** Using aerial photogrammetry to detect significant canopy height change resulting from
  beaver foraging.
- **Authors:** Graham, Benaud, Cunliffe, Puttock, Chant, Elliott, Anderson, Brazier (University of Exeter).
- **Repository:** PANGAEA, doi:10.1594/PANGAEA.939231. Code: Zenodo doi:10.5281/zenodo.5500199
  and doi:10.5281/zenodo.5500203.
- **Licence:** **CC BY 4.0**.
- **Fit:** RGB, DEM. Only two epochs; good for vegetation change (canopy loss from foraging),
  less for trail dynamics. Note the PANGAEA record itself is a table (3,311 rows); the rasters
  and point clouds are linked from it.
- **Link:** https://doi.pangaea.de/10.1594/PANGAEA.939231

### A4. Red Canyon Creek, Wyoming (2018, 2019)
- [x] Checked
- **What:** Collection of four resources: topographic survey data (2018–2019), DEMs
  (2018–2019), shapefiles, water levels (2017–2019). Orthomosaics are in a linked Zenodo record.
  Beaver dam analogues (BDAs) installed 2018; channel re-measured July 2019.
- **Authors:** Davis, Lautz, Kelleher, Vidon, Pearce, Russoniello.
- **Repository:** HydroShare doi:10.4211/hs.7c4ae80863174acfb571ccf8bdac8968; orthomosaics
  doi:10.5281/zenodo.7493152.
- **Licence:** **CC BY 4.0**.
- **Fit:** DEM, RGB. BDAs are human-built, not beaver-built. Resource has no active owner
  (contact CUAHSI for questions).
- **Link:** https://www.hydroshare.org/resource/7c4ae80863174acfb571ccf8bdac8968

---

## B. Dam inventories and time series (NET)

### B1. Kotzebue, NW Baldwin Peninsula, Alaska (2002 to 2019)
- [x] Checked
- **What:** Beaver dam locations mapped from sub-metre satellite imagery for 12 years between
  2002 and 2019, ~100 km² study area. Single zipped file.
- **Authors:** Jones, Tape, Clark, Nitze, Grosse, Disbrow.
- **DOI:** 10.18739/A2TB0XV89 (NSF Arctic Data Center).
- **Licence:** **CC BY 4.0**.
- **Fit:** NET. Multi-year growth of a dam network: ideal for graph dynamics and NBM prediction.
  Same region as Fig. 2A of the IROS paper.
- **Links:**
  - https://arcticdata.io/catalog/view/doi:10.18739/A2TB0XV89
  - https://apgc.awi.de/dataset/bdl-si-rs-2002-2019-kotzebue-nw-bp-alaska
  - Surface water areas, same region: https://apgc.awi.de/dataset/swa-si-rs-2002-2019-kotzebue-nw-bp-alaska

### B1b. Northern Baldwin Peninsula dam locations (2010 to 2019)
- [ ] Checked (record found, contents not read)
- **What:** Companion dataset to B1 covering ~430 km².
- **DOI:** 10.18739/A2CZ3253W. Also https://apgc.awi.de/de/dataset/bdl-si-rs-2010-2019-n-bp-alaska

### B1c. Beaver dam establishment and abandonment, Seward and Baldwin Peninsulas (2001 to 2024)
- [ ] Checked (record found, contents not read)
- **What:** When dams appeared and were abandoned across both peninsulas over 24 years.
- **DOI:** 10.18739/A2SF2MD9Q.
- **Fit:** NET, the longest dam time series found; links the A2 drone sites to regional dynamics.

### B2. EEAGER dam traces, western US (Fairfax, 2025)
- [x] Checked
- **What:** Two KMZ files: dam outlines mapped for Fairfax et al. 2023 (EEAGER), and a
  supplemental set of Wyoming dams and ponds. Bounding box ~30.6–48.4°N, 126.8–99.6°W.
  Number of dams and source imagery years not stated on the record. Total < 1 MB.
- **Repository:** HydroShare (no active owner; contact CUAHSI).
- **Licence:** **CC BY-NC 4.0** (fine for academic use).
- **Fit:** NET, training labels.
- **Link:** https://www.hydroshare.org/resource/f078d94b1f99460f8f374dbe018a01bc/

### B3. Wyoming BRAT calibration and validation data (Andruss, 2026)
- [ ] Checked
- **What:** BRAT outputs under several calibration approaches; per-reach attributes, modelled dam
  capacity, observed dams per km, dam locations; R scripts.
- **Repository:** HydroShare.
- **Licence:** CC BY 4.0.
- **Fit:** NET, benchmark for comparing BeaverSim to BRAT.
- **Link:** https://hydroshare.org/resource/495bc1c63d064fb2b7d16fa859f67f84

### B4. Ontario Beaver Dam (Government of Ontario)
- [ ] Checked
- **What:** Vector line features of beaver dams. No longer updated (historical).
- **Licence:** Open Government Licence, Ontario.
- **Fit:** NET (static, large area).
- **Link:** https://open.canada.ca/data/en/dataset/b44984f7-9ba6-45aa-b25b-a6dc596afea5

### B5. Tierra del Fuego archipelago (Huertas Herrera et al., 2020)
- [ ] Checked
- **What:** 206,203 dams (active and abandoned) mapped visually from Bing, Google Earth and HERE
  imagery (2002 to 2019); 1 km² density raster; drone and field checks in Argentina.
- **Data:** Not deposited publicly. Contact authors (CADIC-CONICET).
- **Fit:** NET (very large scale, invasive range).
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC7182182

### B6. Tayside beaver surveys, Scotland (NatureScot via NBN Atlas)
- [ ] Checked
- **What:** Field survey records of beaver signs, 2017 to 2018 and 2020 to 2021, Tayside (includes Bamff area).
- **Fit:** Ground truth to pair with Scottish public lidar.
- **Links:**
  - https://registry.nbnatlas.org/public/show/dr1920
  - https://registry.nbnatlas.org/public/show/dr2697

---

## C. National aerial orthophoto programmes (open, repeated, 8–30 cm)

Government aerial surveys re-fly whole countries on a regular cycle. Coarser than drones but
with clean licences, full coverage and multi-year archives. Combined with beaver field records
(B6) or dam inventories, they give open time series anywhere beavers occur in these countries.

### C1. Netherlands: Beeldmateriaal Nederland (PDOK)
- [x] Checked (government dataset listings)
- **What:** National aerial orthophotos, two campaigns a year: winter/spring high resolution
  **8 cm** RGB and colour-infrared (7.5 cm before 2025; 5 cm over selected areas), and a summer
  campaign at ~25 cm.
- **Licence:** **CC BY 4.0**.
- **Access:** PDOK (national geoportal), data.overheid.nl.
- **Fit:** RGB (+ NIR from colour-infrared), yearly time series. Beavers widespread.
- **Links:** https://data.overheid.nl/en/dataset/58529-luchtfoto-beeldmateriaal-2025-5cm---7-5cm-infrarood-open-data
  · https://data.overheid.nl/dataset/77581-luchtfoto-beeldmateriaal-2026-5cm---8cm-rgb-open-data

### C2. Switzerland: SWISSIMAGE 10 cm (swisstopo)
- [x] Checked (licence; archive depth to confirm)
- **What:** National orthophoto mosaic, **10 cm** in lowlands and main Alpine valleys, 25 cm in
  the Alps; mosaic updated yearly. Current generation flown from 2017.
- **Licence:** swisstopo free geodata: use, redistribution, processing and commercial use allowed,
  **attribution required**.
- **Access:** swisstopo, Google Earth Engine (`Switzerland/SWISSIMAGE/orthos/10cm`), Swiss Data Cube.
- **Fit:** RGB time series; pairs with swissALTI3D (0.5 m DEM, not verified here). Beavers widespread.
- **Links:** https://www.swisstopo.admin.ch/dam/de/sd-web/WchyQCcLkyd9/Produktinfo_SWISSIMAGE10cm_DE.pdf
  · https://developers.google.com/earth-engine/datasets/catalog/Switzerland_SWISSIMAGE_orthos_10cm

### C3. USA: NAIP (USDA National Agriculture Imagery Program)
- [x] Checked (Montana collections; licence statement to confirm with USDA)
- **What:** Statewide 4-band (RGB + NIR) orthophotos, re-flown about every two years.
  Montana: 2013 (1 m), 2015 (~1 m, incomplete), 2019 (60 cm, gaps filled in 2020), 2021
  (60 cm), **2025 (30 cm, statewide)**.
- **Licence:** US federal imagery, generally public domain (confirm USDA's statement).
- **Access:** Montana State Library (county mosaics, MrSID), USDA NRCS Geospatial Data Gateway,
  cloud catalogues (Planetary Computer, Earth Engine, AWS).
- **Fit:** RGB + NIR (real NDVI), multi-year at ~0.3–1 m: ponds and large dams visible, trails
  not. EEAGER (F1) was built on this kind of imagery.
- **Watch out:** Covers tribal lands too; the licence does not settle data governance (see Notes).
- **Links:** https://msl.mt.gov/geoinfo/data/Aerial_Photos/ · https://msl.mt.gov/geoinfo/data/Aerial_Photos/NAIP_2025

### C4. To check
- [ ] Denmark (national orthophotos, yearly), German states (e.g. NRW 10 cm DOP),
  Flanders, Scotland (Remote Sensing Portal): open aerial programmes reported but not verified here.

---

## D. National lidar (DEM backbone)

Not verified in this session; confirm current terms. Typically ~1 m: good for ponds, canals and
dam capacity, too coarse for 30 cm trails.

- [ ] England: Environment Agency National LiDAR Programme (1 m; ~4 pts/m², per Broughton et al. 2025)
- [ ] Scotland: National Land LiDAR Programme (launched 2025) and Scottish Remote Sensing Portal
- [ ] USA: USGS 3DEP
- [ ] Netherlands: AHN (dense point clouds; beavers widespread)
- [ ] Switzerland: swissALTI3D / swissSURFACE3D
- [ ] Finland, Poland, Denmark: national open lidar

---

## E. Viewers and commercial programmes

### E1. Google Earth Pro (historical imagery)
- [x] Checked (terms)
- **What:** Desktop viewer with a historical imagery slider. In many US areas the imagery is
  ~30–60 cm (NAIP and commercial satellites), with several dates per location.
- **Terms (Google geo guidelines):** Google Earth content may be used for research, education
  and non-profit purposes without permission, with **attribution**; you may export "a handful of
  static images" for non-commercial use; outputs may not be used to reconstruct 3D models or
  "create similar content". Bulk extraction is not covered.
- **Use for us:** scouting only: find sites, see which dates exist, check dam history quickly,
  make an occasional attributed figure. Build datasets from the open source behind the imagery
  (NAIP, national orthophotos), not from Google Earth exports.
- **Link:** https://about.google/brand-resource-center/products-and-services/geo-guidelines/

### E2. Planet Education and Research programme
- [x] Checked (programme page; terms change, confirm before applying)
- **What:** Free Basic tier for university researchers: PlanetScope (~3 m, near-daily) and
  RapidEye, up to 3,000 km²/month, 30-day delay, non-commercial. Paid Research (~$15k/yr) and
  Campus (~$35k/yr, adds SkySat ~50 cm archive) tiers. Sources disagree on whether SkySat is
  included for free.
- **Fit:** dense time series of pond extent and vegetation at 3 m; too coarse for dams and trails.
- **Watch out:** licence restricts redistribution of the imagery itself.
- **Link:** https://planet.com/markets/education-and-research/

---

## F. Models and code

### F1. EEAGER (Fairfax et al. 2023)
- [x] Checked
- **What:** Neural network that detects beaver complexes in aerial and satellite imagery.
  Trained in the western US on 13,344 known dam locations and 56,728 locations without dams;
  evaluated in 12 held-out regions (accuracy 98.5 %, recall 63 %, precision 26 %: tuned to find
  most complexes at the cost of false positives).
- **Paper:** *EEAGER: A Neural Network Model for Finding Beaver Complexes in Satellite and Aerial
  Imagery*, JGR Biogeosciences, doi:10.1029/2022JG007196 (CC BY-NC 4.0).
- **Code:** https://github.com/google/project-eager ; results viewer: bit.ly/EEAGER
- **Data:** dam traces in B2.
- **Fit:** detection baseline; a way to find candidate sites in NAIP for new time series.

### F2. Other
- [ ] **Zocco et al. 2025**, Res-UNet for beaver-influenced floodplain inundation, Connecticut
  (IJGI 14(10):383). Data release not confirmed: https://www.mdpi.com/2220-9964/14/10/383
- [ ] **Diez-Pastor et al. 2025**, semantic segmentation of herbivore trails (closest analogue to
  beaver trails). No dataset link found; contact authors: https://arxiv.org/abs/2504.12121v3
- [ ] **Graham et al. SfM processing code** (Zenodo, see A3)

---

## G. Montana-specific

### G1. Montana Natural Heritage Program dashboards
- [x] Checked
- **What:** The only beaver-related tool is the **Montana Beaver Restoration Hub**: BRAT full
  application and component dashboards (dam-building capacity, potential for conflict,
  management options) on ArcGIS Online. Other dashboards cover species, invasives and NLCD land
  cover. No imagery.
- **Access:** ArcGIS Online; a subset is viewable without an account, full access needs a state
  agency account or contact with Torrey Ritter (FWP). No download terms stated.
- **Fit:** BRAT comparison for Montana reaches.
- **Link:** https://mtnhp.mt.gov/webapps/dashboards

---

## Notes

- A CC BY or public-domain licence settles copyright, not Indigenous data governance. Check land
  status for every site before publishing figures. This applies to public imagery too: NAIP
  covers the Blackfeet sites, and the Alaska sites may be on Alaska Native corporation lands
  (not stated in the ABON metadata).
- Get data-use terms in writing for any dataset obtained directly from people rather than a repository.
- Fairfax is a co-author on Jordan Kennedy's 2024 bioRxiv paper: approach on EEAGER and UK results only.
- Time scales differ: our 2018 data is weekly within one season; the Alaska series (A2, B1, B1c)
  is yearly over 4–24 years; national orthophotos (C) are yearly to biennial. The simulator's
  5–10 year horizon fits the yearly series better than the weekly one.
