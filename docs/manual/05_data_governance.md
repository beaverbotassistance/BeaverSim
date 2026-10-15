# 5. Data governance: licences, land, Indigenous data

Data about a landscape are also data about the people who own, manage or live on it. Who may use them,
for what, and who decides, are questions the files cannot answer and code must not guess. This chapter
explains licences, land status and Indigenous data governance, and how the pipeline keeps these decisions
in human hands: it records them, shows where they are missing, and never fills them in itself.

## You will learn

- What a data licence allows, and what "no licence" means
- What the FAIR and CARE principles ask of a data pipeline
- Why land status, governance and colonies are entered only by a person, and how
- How the pipeline records, checks and reports these decisions

## 1. Licences

A licence says what others may do with the data. Most open scientific data use the
[Creative Commons licences](https://creativecommons.org/licenses/):

| Licence | Allows | Our datasets |
|---|---|---|
| [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) | anything; the authors waive their rights | four Arctic Data Center datasets (Seward Peninsula drone surveys, dam establishment) |
| [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | anything, with attribution | six datasets (Kotzebue and Baldwin dams, Red Canyon on Zenodo and HydroShare, Wyoming BRAT, PANGAEA River Tale) |
| [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) | anything non-commercial, with attribution | EEAGER beaver dam traces |
| [Open Government Licence – Ontario](https://www.ontario.ca/page/open-government-licence-ontario) | use with attribution, under Ontario's terms | Ontario beaver dams |

Data **without** a licence are not free to use: by default, nobody may reuse them without the owners'
permission ([choosealicense.com, no permission](https://choosealicense.com/no-permission/)). Our field data
from Montana have no licence yet.

**In the pipeline**, the licence is read from the repository's record and written as an
[SPDX identifier](https://spdx.org/licenses/) (`CC0-1.0`, `CC-BY-4.0`), with source `repository`; a licence
without an SPDX identifier gets a `LicenseRef-` one (`LicenseRef-OGL-Ontario-1.0`). Each record format has its
own mapping (for EML, `LICENCES` in [`readers/eml.py`](../../data_acquisition/readers/eml.py)); a licence the
mapping does not know is left empty, never guessed. Data without a record have no licence in the catalogue, and
it is listed as missing. A site collection takes its items' licence when they all share one, and says `various`
otherwise, including when they have none; the STAC specification now deprecates `various`, and recommends an
SPDX expression for several licences and `other`, meaning no rights granted, for none
([STAC collection spec](https://github.com/radiantearth/stac-spec/blob/master/collection-spec/collection-spec.md)).

## 2. FAIR and CARE

Two sets of principles shape how research data should be handled:

- **FAIR**: data should be **F**indable, **A**ccessible, **I**nteroperable and **R**eusable
  ([Wilkinson et al. 2016](https://doi.org/10.1038/sdata.2016.18); [GO FAIR](https://www.go-fair.org/fair-principles/)).
  Catalogues with standard metadata, identifiers and licences (chapter 4) serve these.
- **CARE**, the principles for Indigenous data governance: **C**ollective benefit, **A**uthority to control,
  **R**esponsibility and **E**thics ([Carroll et al. 2020](https://doi.org/10.5334/dsj-2020-043);
  [Global Indigenous Data Alliance](https://www.gida-global.org/)). They complement FAIR: data about Indigenous
  lands and communities should benefit those communities, and the communities have the authority to decide
  how the data are used.

The two can pull in different directions: making data maximally open (FAIR) is not always the right choice for
data about Indigenous lands (CARE). That decision belongs to the people concerned, not to a pipeline.

## 3. Land status and governance

For every site, someone has to know:

- **land status**: who owns or manages the land (public agency, private owner, tribal nation), and who to ask;
- **governance**: who may use the data and how: data-use agreements, the community's say for Indigenous lands,
  approvals needed before publication;
- **colonies**: which beaver colonies are at the site, and their extent, an ecological judgement.

None of these can be read from the files. Boundaries can be checked against official maps (in the United
States, for example, the Census Bureau's [TIGER/Line files](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html)
include American Indian areas), but what follows from them, such as whose permission is needed, has to come
from the people involved.

## 4. How the pipeline handles them

- **Only in the site registry**, [`data_acquisition/sites.yaml`](../../data_acquisition/sites.yaml), one entry
  per site, each field either `null` (unknown) or `{value, by, date[, note]}`: what was decided, by whom, when.
  The registry check refuses anything else ([`summary.check_sites`](../../data_acquisition/catalog/summary.py)).
- **Summaries may only suggest.** A dataset summary may give `hints` for a site, with their source, but any other
  key under a site **blocks** the summary ("only hints belong in a summary"). Claude, which drafts summaries,
  therefore never sets these fields.
- **`curate` copies the registry into the items**, recording who entered each value: source `manual`, or
  `claude` if the `by` names Claude ([`curate._set_entered`](../../data_acquisition/steps/curate.py)).
- **Missing never blocks.** A `null` field is listed as missing in `curate_report.csv` and in `sites.json`, so
  the gaps stay visible without stopping the catalogue.

## Case: Rumney Ranch

Rumney Ranch's registry entry has `colonies`, `land_status` and `governance` all `null`. The summary's hints,
drafted by Claude, note that nothing in the files states who owns the land or what agreement covers the data,
and that whether the ranch lies within the Blackfeet Indian Reservation is general knowledge still to be
verified, not something any file states. Until it is settled, the repository stays private and the course's
Montana extract is marked internal ([its README](data/montana_extract/README.md)). This is the pipeline working
as intended: the gap is recorded, visible, and left to the people who can close it.

## Exercises

Notebook: [`notebooks/05_data_governance.ipynb`](notebooks/05_data_governance.ipynb) (work in a copy); solutions
in [`solutions/notebooks/05_data_governance.ipynb`](solutions/notebooks/05_data_governance.ipynb).

1. **Licences from records.** Read the sample's `metadata.xml` with `eml.read` and print its licence. Change the
   licence URL in the text to CC BY-SA 4.0, then to a licence the reader does not know: what does it return?
2. **A registry entry.** In a copy of the sample's site registry, set `land_status` to
   `{value: ..., by: <you>, date: <today>, note: ...}` and check the registry with `summaries.check_sites`. Then
   try an entry without `by`.
3. **From registry to items.** Build and curate the sample with your registry (point `BEAVER_SITES` to it). What
   does the orthomosaic item say about `land_status`, and where did the value come from (`beaver:origin`)? What
   changes if `by` is `claude`?
4. **Hints only.** Add `land_status: private` under the site in a copy of the reference summary (next to
   `hints`). What does the check say?
5. **Find it in the code.** Where does `curate` copy the registry's fields into items, and where does a site
   collection's licence become `various`?

## Where this lives

- [`data_acquisition/sites.yaml`](../../data_acquisition/sites.yaml): the site registry.
- [`data_acquisition/catalog/summary.py`](../../data_acquisition/catalog/summary.py): `check_sites`, `MANUAL_SITE_FIELDS`,
  the "only hints" rule in `check`, `by_claude`.
- [`data_acquisition/steps/curate.py`](../../data_acquisition/steps/curate.py): `MANUAL_FIELDS`, `_set_entered`, `curate_item`.
- [`data_acquisition/readers/eml.py`](../../data_acquisition/readers/eml.py) (`LICENCES`) and the other record readers.
- [`data_acquisition/catalog/build.py`](../../data_acquisition/catalog/build.py): the collection licence in `build`.
- [`data_acquisition/catalog/root.py`](../../data_acquisition/catalog/root.py): missing site fields in `sites.json`.

## Sources

- Creative Commons, [licences](https://creativecommons.org/licenses/), [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/),
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/);
  Government of Ontario, [Open Government Licence](https://www.ontario.ca/page/open-government-licence-ontario);
  [SPDX licence list](https://spdx.org/licenses/); [choosealicense.com, no permission](https://choosealicense.com/no-permission/)
- M. D. Wilkinson et al., [The FAIR Guiding Principles for scientific data management and stewardship](https://doi.org/10.1038/sdata.2016.18),
  Scientific Data, 2016; [GO FAIR](https://www.go-fair.org/fair-principles/)
- S. R. Carroll et al., [The CARE Principles for Indigenous Data Governance](https://doi.org/10.5334/dsj-2020-043), Data Science
  Journal, 2020; [Global Indigenous Data Alliance](https://www.gida-global.org/)
- U.S. Census Bureau, [TIGER/Line files](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html)
