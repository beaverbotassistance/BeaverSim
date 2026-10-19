# C. Conventions

The rules the pipeline and its data follow, in one place. Each links to where it is explained.

## Data

- **Never write to the originals.** Downloaded and extracted files are read-only; the field-season folders are only
  read, and `beaver_dataset/` holds links, exported layers and written sidecars, all recorded
  ([chapters 8](08_open_datasets.md), [11](11_field_data.md), [17](17_field_step_internals.md)).
- **Summaries, layout files and the site registry are data, not code.** Everything specific to one dataset or site
  lives there; code is organised by data type and metadata standard ([chapter 19](19_extending.md)).
- **Nothing is guessed.** An unknown value stays empty (None, `null`) with an open question; a disagreement between
  sources is flagged, not resolved silently ([chapter 9](09_describing_a_dataset.md)).
- **Every value says where it came from**: `auto`, `build`, `repository`, `claude` or `manual`
  ([chapter 15](15_curate.md)).
- **Units and dates**: SI units (metres; other units recorded and converted later), dates as ISO 8601
  (`YYYY-MM-DD`; [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339), the open profile of ISO 8601), with a precision when only the month or
  year is known ([chapter 14](14_builder.md)).

## Review marks

| Where | Mark | Set by |
|---|---|---|
| a summary, a layout file | `authored: {by, date[, model]}`; `reviewed: {by, date}` once a person has checked it | Claude or a person writes `authored`; **only a person** sets `reviewed` |
| a registry field (colonies, land status, governance) | `{value, by, date[, note]}`; `null` while unknown | the person (or Claude, labelled so) who entered it |
| a registry site | `confirmed: {by, date}` | a person who checked the site's identity |
| an annotation, an item | `needs_inspection` flag | a summary's `inspect`; cleared only by a person (milestone 8) |

A value written by Claude is labelled `claude` in the catalogue until a person reviews it; the field step refuses to
build from a layout file that is not reviewed ([chapters 9](09_describing_a_dataset.md), [11](11_field_data.md)).

## Names

- **Slugs** (datasets, sites): lower case, words joined by `_`, e.g. `rumney_ranch`, `arcticdata_baldwin_dams`.
- **Dataset folders**: `doi_<doi>` or `id_<identifier>` under the repository's folder ([chapter 16](16_sources.md)).
- **Item ids**: `<site>_<time label>_<product>[_<variant>]` ([chapter 14](14_builder.md)).
- **`beaver_dataset/`**: one folder per survey date, `orthomosaic_part-<n>[_chunk-<k>].tif`,
  `annotations/<date>/<feature>[_points][_colony-<id>][_<variant>].gpkg`
  ([`field_naming.md`](../dataset/field_naming.md)).
- **Quality flags**: `snake_case`, saying what was found (`crs_mismatch`), not what to do.

## Code

- **Readable first**: a module docstring that says what the module does and how to run it; a docstring per public
  function; comments only where the code cannot say why.
- **Lines** up to 120 characters; type hints from `typing` (`List`, `Dict`, `Optional`), as the existing code; the
  lint rules `E`, `F`, `W` ([chapter 18](18_testing.md)).
- **Constants** (thresholds, limits) named at the top of the module, with a comment on why that value.
- **No silent failures**: a file that cannot be read is reported (`unsupported`, `unreadable`), not skipped quietly.
- **Tests on synthetic data** for every behaviour; the regression snapshot for every change
  ([chapter 18](18_testing.md)).

## Commits

- Messages start with the kind of change, after [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):
  `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`; then one line saying what changed, in plain words.
- One logical change per commit, with its tests and the documents it touched.
- Commits are authored by the person responsible for them, who has reviewed what they commit.
- Large data stays out of git. The course's Montana extract (about 4 MB) is the exception, made on purpose small;
  CSV files go through Git LFS ([appendix B](B_troubleshooting.md)).
- The repository is private while the governance of the Montana data is settled ([chapter 5](05_data_governance.md)):
  nothing from it is published or shared outside the project.
