"""The version must agree everywhere it is written down."""

import re
from pathlib import Path

import pytest

from prime_lc_lcd import __version__

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        pytest.skip(f"{rel} not shipped here (installed-package test run)")
    return path.read_text()


def test_debian_changelog_matches():
    upstream = re.match(r"prime-lc-lcd \(([^)]+)-[^-)]+\)", _read("debian/changelog"))[1]
    assert upstream.split("~")[0] == __version__


def test_man_page_matches():
    assert f'"prime-lc-lcd {__version__}"' in _read("packaging/prime-lc-lcd.1")


def test_changelog_has_an_entry():
    assert f"## {__version__} - " in _read("CHANGELOG.md")
