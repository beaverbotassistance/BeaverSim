# Building and curating catalogues

> Status: outline. Learning goals, sections and exercises; the text is still to be written.

## You will learn

- Build a catalogue and read its report
- Run `curate` and read its flags
- Build the root catalogue and the site index

## Sections

1. `build`: one item per file (or layer, or photo folder); the build report
2. Quality flags: where they come from (build, repository, auto, claude, manual)
3. `curate`: automatic checks, `--verify`
4. The root catalogue and `sites.json`
5. Rebuilding after a change

## Exercises

1. Build and curate the sample catalogue; explain each flag.
2. Make a flag appear on purpose and trace which code raised it.

## Where this lives

- [`data_acquisition/catalog/build.py`](../../data_acquisition/catalog/build.py)
- [`data_acquisition/steps/curate.py`](../../data_acquisition/steps/curate.py)
- [`data_acquisition/catalog/root.py`](../../data_acquisition/catalog/root.py)

## Sources

- (links to the sources of each concept, checked when the chapter is written)
