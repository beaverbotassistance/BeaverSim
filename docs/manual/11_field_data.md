# Field data: from a field drive to `beaver_dataset/`

> Status: outline. Learning goals, sections and exercises; the text is still to be written.

## You will learn

- Know why field data needs a layout step before the pipeline
- Read and review a layout file
- Run the field step and check its records
- Read the alignment check and the `needs_inspection` flag

## Sections

1. The field-season drive and its inventory (`field_inventory`, `field_audit`)
2. Layout files and the naming policy
3. Links vs written files: what is never changed
4. Applying ArcGIS georeferencing; CRS corrections
5. The alignment check and the contact sheet
6. Case: Rumney Ranch, from the drive to a catalogue of 420 items

## Exercises

1. Read the Rumney layout entries for one survey and find each file in the extract.
2. Run the alignment check on the extract; read its medians.

## Where this lives

- [`data_acquisition/sources/field_inventory.py`](../../data_acquisition/sources/field_inventory.py)
- [`data_acquisition/sources/field.py`](../../data_acquisition/sources/field.py)
- [`data_acquisition/sources/field_alignment.py`](../../data_acquisition/sources/field_alignment.py)
- [`data_acquisition/field_layouts/`](../../data_acquisition/field_layouts/)
- [`docs/dataset/field_naming.md`](../../docs/dataset/field_naming.md)

## Sources

- (links to the sources of each concept, checked when the chapter is written)
