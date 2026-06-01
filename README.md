# bioledger-isatab-library

Curated collection of **ISA-Tab studies** for use with
[`bioledger`](../bioledger). Pull a study into your local BioLedger
install to bring along the metadata, sample structure, and file
manifests without re-authoring them.

## Status

**Alpha.** Three validated studies ship today (see [Studies](#studies)).
More are added as they're authored and validated.

## Relationship to other repos

```
bioledger-isatab-schema    ← defines the validation rules
        │
        ▼
bioledger-isatab-library   ← THIS REPO: instances of valid studies
        │
        ▼
bioledger                  ← consumes studies at runtime
```

- The pydantic models + `validate_isatab` live in
  [`bioledger-isatab-schema`](../bioledger-isatab-schema). This repo's CI
  imports them to validate every committed study.
- BioLedger-flavored validation is stricter than plain `isatools.load`:
  it enforces at least one assay with data files, organism characteristic
  in sources, assay technology type, etc. See the schema repo's README
  for the full contract.

CI installs `bioledger-isatab-schema` from its own repo
(`bioledger-project/isatab-schema`, checked out into `.schema`) and imports
`bioledger_isatab_schema` to validate every committed study.

## Studies

| Directory | Type | Organism | Source |
|---|---|---|---|
| `GCF_000002765.6` | reference_genome | *Plasmodium falciparum* 3D7 | NCBI RefSeq (genome FASTA + GFF) |
| `GCF_000227135.1` | reference_genome | *Leishmania donovani* BPK282A1 | NCBI RefSeq (genome FASTA + GFF) |
| `PRJNA450813` | experimental_data | *Leishmania donovani* (CL/VL/IV) | ENA paired-end Illumina FASTQ |

The *P. falciparum* experimental reads (ENA `PRJEB2146`, 3D7×HB3 cross) are
**not yet included**: the 3D7 parent run cannot be identified from ENA
metadata alone (sample aliases are internal Sanger IDs). It needs the
Miles et al. 2016 Supplementary Table S1 mapping to pin the exact run
accession(s) — tracked in Open Questions.

## Directory layout

```
bioledger-isatab-library/
├── README.md
├── pyproject.toml                       # dev/test deps only
├── studies/                             # top level: one dir per study
│   ├── <study_slug>/
│   │   ├── i_investigation.txt          # required, ISA-Tab spec
│   │   ├── s_*.txt                      # study table(s)
│   │   ├── a_*.txt                      # assay table(s)
│   │   └── manifest.yaml                # REQUIRED: download URLs + checksums
│   └── ...
├── conftest.py                          # path-addressable collector (repo root)
└── .github/workflows/ci.yml
```

### Conventions

- **One directory per study.** The directory name (`<study_slug>`) is the
  canonical handle for that study and SHOULD match the
  `Study Identifier` in `i_investigation.txt`. CI enforces this.
- **ISA-Tab files live at the root of the study directory** so plain
  `isatools.load(study_dir)` works without any rewrites.
- **The ISA-Tab assay table lists plain filenames** (no URLs), keeping it
  standards-compliant and portable to any ISA tool.
- **`manifest.yaml` is required and owns all downloads.** It is the single
  source of truth for each file's `url` and checksum (`sha256` and/or
  `md5`; at least one, verified after download). Every manifest `filename`
  must also appear in the ISA-Tab assay/study tables — CI cross-checks this.
- **No PII or restricted data**, ever. This repo is intended to be
  publishable.

## Authoring a study

1. Decide whether you're adopting an existing public ISA-Tab bundle or
   authoring from scratch.
2. Drop the ISA-Tab files into `studies/<study_slug>/`.
3. Run `pytest studies/<study_slug>/` locally to validate.
4. Add a `README.md` for the study capturing description, citation,
   license.
5. Open a PR. CI will validate just your study by default.

## Testing framework

Same philosophy as
[`bioledger-toolspec-library`](../bioledger-toolspec-library): **changing
a study always tests that study, automatically** — no markers, labels, or
schedules.

### Per-study checks (always-on)

For every `studies/<study_slug>/`:

1. `i_investigation.txt` exists and `isatools.load` succeeds.
2. `validate_isatab(study_dir).is_valid` is true (zero ERROR-severity
   issues from the BioLedger-flavored validator).
3. The directory name matches the study identifier.
4. `manifest.yaml` exists and passes `validate_manifest` (study_type set,
   accession matches the directory name, every file has
   filename/url/format and at least one checksum).
5. Every manifest `filename` is referenced in the ISA-Tab assay/study
   tables (`a_*.txt` / `s_*.txt`).
6. (Soft) Warning-level checks (organism present, assay technology type
   set, accession/study_type prefix consistency) are reported but not
   failing. We tighten over time.

Validation is **offline**: no files are downloaded during CI. Checksums
are verified at download time by `bioledger_isatab_schema.download_manifest`.

### Targeted runs (CLI)

A `conftest.py` collector at the repo root makes each study directory
addressable as a pytest path:

```bash
pytest                          # all studies
pytest studies/<slug>/          # one study
```

### CI: changed-only by default, full sweep on main

`.github/workflows/ci.yml` mirrors the toolspec-library workflow:

1. Compute changed paths via `git diff` against the PR base.
2. Map them to touched study dirs (anything under `studies/<slug>/`
   triggers that slug; changes to `conftest.py`, `pyproject.toml`, or the
   workflow trigger **everything**).
3. Run `pytest` against the touched dirs.

On pushes to `main` and on a nightly schedule, run the full suite as a
safety net (catches things like manifest URLs going dead).

## Local development

```bash
# from this repo's root
pip install -e .                                  # installs test deps
pip install -e ../bioledger-isatab-schema         # editable schema (or ../bioledger pre-extraction)
pytest                                            # full sweep
pytest studies/<slug>/                            # one study
```

## Open questions / TODOs

- [ ] Add the *P. falciparum* `PRJEB2146` experimental study once the 3D7
      parent run accession(s) are pinned from Miles et al. 2016 Table S1.
- [ ] Decide whether to ship a `family.yaml`-style grouping for related
      studies (e.g. all studies from one consortium); punt until needed.
