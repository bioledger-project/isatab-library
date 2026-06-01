"""Path-addressable pytest collector for ISA-Tab studies.

Lives at the repo root so its ``pytest_collect_file`` hook fires while pytest
walks ``studies/``. Emits one validation item per study directory. Allows:
- pytest                       # all studies
- pytest studies/<accession>/  # one study
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Repo root (this file lives at the repo root).
ROOT = Path(__file__).parent
STUDIES_DIR = ROOT / "studies"


def pytest_collect_file(parent, file_path: Path):
    """Collect each study via its i_investigation.txt entry point (pytest >= 8 API)."""
    try:
        rel_path = file_path.relative_to(ROOT)
    except ValueError:
        return
    if rel_path.parts[:1] != ("studies",):
        return
    if file_path.name == "i_investigation.txt":
        return StudyFile.from_parent(parent, path=file_path)


class StudyFile(pytest.File):
    """An i_investigation.txt file representing a study."""

    def collect(self):
        study_dir = self.path.parent
        yield StudyValidationItem.from_parent(
            self, name=f"{study_dir.name}::validate", study_dir=study_dir
        )


def _assay_table_filenames(study_dir: Path) -> set[str]:
    """Collect every whitespace/tab-delimited token from the study/assay tables.

    Used to cross-check that each manifest ``filename`` is actually referenced
    by the ISA-Tab (the assay table is the canonical list of data files; the
    manifest only adds download URLs + checksums for those same files).
    """
    tokens: set[str] = set()
    for pattern in ("a_*.txt", "s_*.txt"):
        for table in study_dir.glob(pattern):
            for line in table.read_text().splitlines():
                for cell in line.split("\t"):
                    cell = cell.strip().strip('"')
                    if cell:
                        tokens.add(cell)
    return tokens


class StudyValidationItem(pytest.Item):
    """Per-study validation checks."""

    def __init__(self, parent, name, study_dir):
        super().__init__(name, parent)
        self.study_dir = Path(study_dir)

    def runtest(self):
        from bioledger_isatab_schema import (
            Severity,
            load_manifest,
            validate_isatab,
            validate_manifest,
        )

        # 1. i_investigation.txt exists and parses
        inv_file = self.study_dir / "i_investigation.txt"
        if not inv_file.exists():
            raise AssertionError("Missing i_investigation.txt")

        # 2. validate_isatab reports zero ERRORs
        result = validate_isatab(self.study_dir)
        errors = [i for i in result.issues if i.severity == Severity.ERROR]
        if errors:
            raise AssertionError(
                "ISA-Tab validation errors:\n"
                + "\n".join("  {}: {}".format(i.field, i.message) for i in errors)
            )

        # 3. manifest.yaml is REQUIRED and must validate (schema-package check).
        #    validate_manifest enforces study_type, accession==dir name, and
        #    that every file has filename/url/format/sha256.
        manifest_issues = validate_manifest(self.study_dir)
        manifest_errors = [i for i in manifest_issues if i["severity"] == "error"]
        if manifest_errors:
            raise AssertionError(
                "manifest.yaml errors:\n"
                + "\n".join("  {}: {}".format(i["field"], i["message"]) for i in manifest_errors)
            )

        # 4. Cross-check: every manifest filename is referenced by the ISA-Tab.
        manifest = load_manifest(self.study_dir)
        assert manifest is not None  # validate_manifest would have errored otherwise
        referenced = _assay_table_filenames(self.study_dir)
        for f in manifest.files:
            if f.filename not in referenced:
                raise AssertionError(
                    f"manifest file '{f.filename}' is not referenced in any "
                    "ISA-Tab assay/study table (a_*.txt / s_*.txt)"
                )

        # 5. (Soft) warnings - report but don't fail.
        warns = [i for i in result.issues if i.severity == Severity.WARNING]
        warns += [i["message"] for i in manifest_issues if i["severity"] == "warning"]
        if warns:
            print("\n  Warnings:")
            for w in warns:
                msg = w if isinstance(w, str) else "{}: {}".format(w.field, w.message)
                print("    " + msg)

    def reportinfo(self):
        return self.path, 0, f"study: {self.name}"
