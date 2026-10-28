import shutil
from pathlib import Path

import matplotlib
import pytest

# Render without a display; must happen before pyplot is first imported
matplotlib.use("Agg")

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """The Makefile exports these, so keep the host's values out of the tests."""
    for name in ("YEAR", "TYPE", "MODE", "LANGS"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def fixtures_dir():
    return FIXTURES


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Empty working directory with a data/ folder, like the repo root the scripts expect."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    return tmp_path


@pytest.fixture
def stage(workdir):
    """Copy fixture files into the working directory's data/ folder."""

    def _stage(*names):
        for name in names:
            shutil.copy(FIXTURES / name, workdir / "data" / name)

    return _stage
