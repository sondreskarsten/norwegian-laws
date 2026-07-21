"""Tests for lovdata_publisher.git_export."""
from lovdata_publisher.git_export import date_to_git_timestamp


# ─── date_to_git_timestamp ─────────────────────────────────────────────────

class TestDateToGitTimestamp:
    def test_valid_date(self):
        ts = date_to_git_timestamp("2024-01-01")
        assert "+0100" in ts
        assert ts.startswith("1704")

    def test_invalid_date(self):
        ts = date_to_git_timestamp("not-a-date")
        assert "+0100" in ts
