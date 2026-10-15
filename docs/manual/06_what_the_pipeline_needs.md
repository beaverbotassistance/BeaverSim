# What the pipeline needs from you

> Status: outline. Learning goals, sections and exercises; the text is still to be written.

## You will learn

- Know, for every piece of information, who supplies it and whether it is required
- Know where the pipeline stops, where it skips a file and where it only flags
- Know the time information each data file needs

## Sections

1. Four levels: blocks, blocks one step, skips one file, flags only
2. The summary: required fields and their checks
3. Time: day, month, year, a range, or unknown with limits; what is cross-checked against the dates
4. Space: CRS declared or given; when a raster cannot be placed
5. Review marks: `authored`, `reviewed`, and values labelled `claude`
6. Manual fields: colonies, land status, governance, licence
7. The field step: layout files and their review
8. Case: the legacy example datasets, and what they lack to enter the pipeline

## Exercises

1. Break a sample summary in five ways; predict and then check what the pipeline does.
2. Find the check that refuses a summary without a date.

## Where this lives

- [`data_acquisition/catalog/summary.py`](../../data_acquisition/catalog/summary.py)
- [`data_acquisition/catalog/build.py`](../../data_acquisition/catalog/build.py)
- [`data_acquisition/steps/curate.py`](../../data_acquisition/steps/curate.py)
- [`data_acquisition/sources/field.py`](../../data_acquisition/sources/field.py)

## Sources

- (links to the sources of each concept, checked when the chapter is written)
