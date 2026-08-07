import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

import models


@pytest.fixture(autouse=True)
def _reset_bookings():
    models.reset_state()
    yield
    models.reset_state()
