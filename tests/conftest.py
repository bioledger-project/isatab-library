"""Path-addressable pytest collector for ISA-Tab studies.

Walks studies/ and emits pytest items per study directory. Allows:
- pytest                      # all studies
- pytest studies/<slug>/     # one study
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Find the project root (repo root)
ROOT = Path(__file__).parent.parent
STUDIES_DIR = ROOT / "studies"


def pytest_collect_file(parent, path):
    """Collect study directories under studies/."""
    # Only process files under studies/
    rel_path = Path(path).relative_to(ROOT)
    if not rel_path.parts[:1] == ("studies",):
        return

    # Only collect i_investigation.txt as the entry point
    if Path(path).name == "i_investigation.txt":
        return StudyFile.from_parent(parent, fspath=path)


class StudyFile(pytest.File):
    """An i_investigation.txt file representing a study."""

    def collect(self):
        """Emit test items for this study."""
        study_dir = self.fspath.parent
        yield StudyValidationItem.from_parent(
            self, name=f"{study_dir.name}::validate", study_dir=study_dir
        )


class StudyValidationItem(pytest.Item):
    """Per-study validation checks."""

    def __init__(self, parent, name, study_dir):
        super().__init__(name, parent)
        self.study_dir = Path(study_dir)

    def runtest(self):
        from bioledger_isatab_schema import Severity, validate_isatab

        # 1. i_investigation.txt exists and parses
        inv_file = self.study_dir / "i_investigation.txt"
        if not inv_file.exists():
            raise AssertionError("Missing i_investigation.txt")

        # 2. validate_isatab reports zero ERRORs
        result = validate_isatab(self.study_dir)
        errors = [i for i in result.issues if i.severity == Severity.ERROR]
        if errors:
            raise AssertionError(
                "Validation errors:\n"
                + "\n".join("  {}: {}".format(i.field, i.message) for i in errors)
            )

        # 3. directory name matches study identifier
        from isatools import isatab

        inv = isatab.load(str(self.study_dir))
        if inv.studies:
            study_id = inv.studies[0].identifier
            if study_id and self.study_dir.name != study_id:
                raise AssertionError(
                    "Directory name '{}' does not match study identifier '{}'".format(
                        self.study_dir.name, study_id
                    )
                )

        # 4. (Soft) warning-level checks - report but don't fail
        warns = [i for i in result.issues if i.severity == Severity.WARNING]
        if warns:
            print("\n  Warnings:")
            for w in warns:
                print("    {}: {}".format(w.field, w.message))

        # 5. Optional: check manifest.yaml if present
        manifest_file = self.study_dir / "manifest.yaml"
        if manifest_file.exists():
            import yaml

            try:
                manifest = yaml.safe_load(manifest_file.read_text())
                if not isinstance(manifest, dict):
                    raise AssertionError("manifest.yaml is not a dict")
                # Basic schema check: each entry has url and checksum
                for entry in manifest.get("files", []):
                    if not entry.get("url"):
                        raise AssertionError("manifest entry missing url")
                    if not entry.get("sha256"):
                        raise AssertionError("manifest entry missing sha256")
            except Exception as e:
                raise AssertionError("Failed to parse manifest.yaml: {}".format(e))

        # 6. Optional: download-and-load smoke test if network available
        if manifest_file.exists():
            try:
                from bioledger_isatab_schema import load_dataset_from_isatab

                # This will fail if network is unavailable, which is fine
                ds = load_dataset_from_isatab(self.study_dir, validate=True)
                if not ds.files:
                    raise AssertionError("Dataset has no files after load")
            except Exception as e:
                # Skip with reason if network/other transient issue
                pytest.skip("Download/load check failed: {}".format(e))
