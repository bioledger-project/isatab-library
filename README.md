# bioledger-isatab-library

Curated collection of **ISA-Tab studies** for use with
[`bioledger`](../bioledger). Pull a study into your local BioLedger
install to bring along the metadata, sample structure, and file
manifests without re-authoring them.

## Status

**Pre-alpha.** The directory layout and testing framework described below
are the agreed plan; the repo is otherwise empty. Studies will be added
as they're written and validated.

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

While `bioledger-isatab-schema` is still pre-extraction, CI here will
import `bioledger.forges.isaforge.validate` directly from an editable
`../bioledger` checkout.

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
│   │   ├── data/                        # optional small fixture files
│   │   ├── manifest.yaml                # OPTIONAL: remote-file download spec
│   │   └── README.md                    # short description, citation, license
│   └── ...
├── tests/
│   └── conftest.py                      # path-addressable collector
└── .github/workflows/ci.yml
```

### Conventions

- **One directory per study.** The directory name (`<study_slug>`) is the
  canonical handle for that study and SHOULD match the
  `Study Identifier` in `i_investigation.txt`. CI enforces this.
- **ISA-Tab files live at the root of the study directory** so plain
  `isatools.load(study_dir)` works without any rewrites.
- **Each study has a `README.md`** with:
  - one-paragraph description,
  - citation / DOI if applicable,
  - data license,
  - whether `data/` ships in-repo or via `manifest.yaml`.
- **Bundled data goes in `data/`**, only when files are tiny (a few KB).
- **Anything bigger goes in `manifest.yaml`** as a download spec
  (URLs + checksums); the loader/CI fetches on demand. (Concrete
  manifest schema TBD on first study that needs it.)
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
4. If `manifest.yaml` is present, it parses and every entry has a URL
   and a checksum.
5. If `data/` is present, every file referenced in the assay tables
   resolves to either a `data/` file or an entry in `manifest.yaml`.
6. (Soft) Warning-level checks (organism present, assay technology type
   set, etc.) are reported but not initially failing. We tighten over
   time.

### Optional download-and-load check

If a study declares `manifest.yaml` and CI has network access (default
true on GitHub-hosted runners), one tiny smoke test downloads the first
manifest entry, checks the checksum, and asserts
`load_dataset_from_isatab(study_dir)` returns a non-empty `DataSet`.
Skips with a clear reason if the network is unavailable.

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
   triggers that slug; changes to `tests/`, `pyproject.toml`, the
   workflow, or the schema package trigger **everything**).
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

- [ ] Define `manifest.yaml` schema (URL, sha256, size, sample mapping)
      on the first study that needs remote data.
- [ ] Decide whether to ship a `family.yaml`-style grouping for related
      studies (e.g. all studies from one consortium); punt until needed.
- [ ] Once `bioledger-isatab-schema` is extracted, switch CI from
      `bioledger.forges.isaforge.validate` import to
      `bioledger_isatab_schema`.
- [ ] Scaffold `pyproject.toml`, `conftest.py` (path-addressable
      collector), and the GitHub Actions workflow with changed-paths
      discovery.
- [ ] Add the first real study end-to-end as the reference
      implementation.
