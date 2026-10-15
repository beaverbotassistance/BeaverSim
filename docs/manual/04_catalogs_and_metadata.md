# Catalogues and metadata: STAC, records, checksums

> Status: outline. Learning goals, sections and exercises; the text is still to be written.

## You will learn

- Know what a STAC catalogue, collection, item and asset are
- Read a repository's metadata record (EML, DataCite-like JSON)
- Understand DOIs and checksums, and what they prove

## Sections

1. Why catalogue: finding, comparing and trusting data
2. STAC: catalog, collection, item, asset, extensions (proj, raster, eo, file)
3. Metadata records: EML (DataONE), PANGAEA, Zenodo, HydroShare, CKAN
4. Identifiers: DOIs and repository ids
5. Checksums: MD5, SHA-256, multipart ETags; what a match proves
6. The `beaver:` properties of our items

## Exercises

1. Open a sample item JSON and name each part.
2. Validate a catalogue with pystac.
3. Verify a file against its checksum by hand.

## Where this lives

- [`data_acquisition/catalog/stac.py`](../../data_acquisition/catalog/stac.py)
- [`data_acquisition/readers/eml.py`](../../data_acquisition/readers/eml.py)
- [`data_acquisition/sources/checksums.py`](../../data_acquisition/sources/checksums.py)
- [`data_acquisition/catalog/descriptors.py`](../../data_acquisition/catalog/descriptors.py)

## Sources

- (links to the sources of each concept, checked when the chapter is written)
