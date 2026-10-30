"""Legacy reconstruction versions on the law-history branch.

The branch is rebuilt nightly by .github/workflows/law-history.yml, which also
pushes one yearly tag per reconstructed year and a citable build tag
history-YYYY-MM-DD. Version labels are tag names, not verified legal dates.
"""
from datetime import datetime, timezone

FIRST_VERSION_YEAR = 2001


def legacy_version_refs(max_year=None):
    """Map version label to the git ref the reader links to (the tag itself)."""
    if max_year is None:
        max_year = datetime.now(timezone.utc).year
    return {f"v{year}": f"v{year}" for year in range(FIRST_VERSION_YEAR, max_year + 1)}


LEGACY_VERSION_REFS = legacy_version_refs()


def supported_version_tags(requested=None):
    """Return catalog order, optionally narrowed by requested labels."""
    return [tag for tag in LEGACY_VERSION_REFS if requested is None or tag in requested]
