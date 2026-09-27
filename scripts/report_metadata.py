"""Shared report format and installed skill version fields."""
from pathlib import Path
import re


def report_metadata():
    try:
        text = (Path(__file__).resolve().parent.parent / "CHANGELOG.md").read_text(encoding="utf-8")
        match = re.search(r"^## (v\d+)\b", text, re.M)
        version = match.group(1) if match else None
    except (OSError, UnicodeError):
        version = None
    return {"report_version": 1, "skill_version": version}
