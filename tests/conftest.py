"""Wspólne fikstury.

Prywatne `data/pozycje.csv` nie jest częścią repozytorium, więc testy, które
potrzebują prawdziwego zbioru, muszą działać także na świeżym klonie — wtedy
korzystają z pliku przykładowego.
"""

from __future__ import annotations

import pytest

from wycieczki.config import DATA_FILE, EXAMPLE_FILE
from wycieczki.data import load_dataset

HAS_PRIVATE_DATA = DATA_FILE.exists()

needs_private_data = pytest.mark.skipif(
    not HAS_PRIVATE_DATA,
    reason="brak data/pozycje.csv — prywatne dane nie są w repozytorium",
)


@pytest.fixture(scope="session")
def dataset_path():
    """Prawdziwe dane, jeśli są pod ręką; w przeciwnym razie plik przykładowy."""
    return DATA_FILE if HAS_PRIVATE_DATA else EXAMPLE_FILE


@pytest.fixture(scope="session")
def dataset(dataset_path):
    return load_dataset(dataset_path).frame
