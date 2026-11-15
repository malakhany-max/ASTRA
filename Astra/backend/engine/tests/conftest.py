import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def engine_config():
    from astra_engine.config import load_engine_config
    return load_engine_config()
